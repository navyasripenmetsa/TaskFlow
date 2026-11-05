package com.taskflow.mobile

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.taskflow.mobile.data.HandoffParser
import com.taskflow.mobile.model.ActivityHandoff
import com.taskflow.mobile.model.HandoffContext
import com.taskflow.mobile.model.TaskHandoff
import com.taskflow.mobile.model.UnifiedActivityHandoff
import com.taskflow.mobile.reconstruction.UrlReconstructor
import java.io.IOException

class MainActivity : Activity() {
    private lateinit var statusText: TextView
    private lateinit var activityContent: LinearLayout
    private lateinit var urlReconstructor: UrlReconstructor

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        activityContent = findViewById(R.id.activityContent)
        urlReconstructor = UrlReconstructor(this)
        findViewById<Button>(R.id.loadSampleButton).setOnClickListener {
            loadSamplePackage()
        }
        findViewById<Button>(R.id.importJsonButton).setOnClickListener {
            openJsonDocument()
        }
        loadSamplePackage()
    }

    private fun loadSamplePackage() {
        statusText.setText(R.string.loading_package)
        activityContent.removeAllViews()

        val result = try {
            assets.open(SAMPLE_FILE).bufferedReader().use { reader ->
                HandoffParser().parse(reader.readText())
            }
        } catch (error: Exception) {
            Result.failure(error)
        }

        displayResult(result, R.string.package_error)
    }

    private fun openJsonDocument() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "application/json"
        }
        try {
            startActivityForResult(intent, REQUEST_OPEN_JSON)
        } catch (_: ActivityNotFoundException) {
            statusText.setText(R.string.file_picker_unavailable)
        }
    }

    @Deprecated("Use Activity Result APIs when the app adds the AndroidX activity dependency.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_OPEN_JSON || resultCode != RESULT_OK) {
            return
        }

        val uri = data?.data
        if (uri == null) {
            statusText.setText(R.string.file_access_error)
            return
        }

        loadImportedPackage(uri)
    }

    private fun loadImportedPackage(uri: Uri) {
        statusText.setText(R.string.importing_package)
        activityContent.removeAllViews()

        val result = try {
            val inputStream = contentResolver.openInputStream(uri)
                ?: throw IOException("The selected file could not be opened.")
            inputStream.bufferedReader().use { reader ->
                val contents = reader.readText()
                if (contents.isBlank()) {
                    throw IOException("The selected file is empty.")
                }
                HandoffParser().parse(contents)
            }
        } catch (error: SecurityException) {
            Result.failure(IOException("Access to the selected file was denied.", error))
        } catch (error: IOException) {
            Result.failure(error)
        }

        displayResult(result, R.string.import_error)
    }

    private fun displayResult(
        result: Result<com.taskflow.mobile.model.HandoffDocument>,
        errorStringId: Int
    ) {
        result
            .onSuccess { document ->
                statusText.text = getString(
                    R.string.package_loaded,
                    document.activities.size
                )
                document.activities.forEach(::renderActivity)
            }
            .onFailure { error ->
                statusText.text = getString(
                    errorStringId,
                    error.message ?: getString(R.string.unknown_error)
                )
            }
    }

    private fun renderActivity(activity: ActivityHandoff) {
        addText(activity.activityLabel, 24f, true)
        addText(getString(R.string.activity_id, activity.activityId), 14f, false)

        activity.handoffPackages.forEach(::renderTask)
        activity.activityHandoffPackage?.let(::renderUnifiedActivity)
    }

    private fun renderUnifiedActivity(activityPackage: UnifiedActivityHandoff) {
        addText(activityPackage.activityLabel, 20f, true)
        addText(activityPackage.activityDescription, 14f, false)
        addText(
            getString(R.string.activity_context_count, activityPackage.contexts.size),
            14f,
            true
        )
        activityPackage.contexts.forEach(::renderContext)
    }

    private fun renderTask(task: TaskHandoff) {
        addText(task.taskLabel, 20f, true)
        addText(task.taskDescription, 14f, false)
        addText(getString(R.string.context_count, task.contexts.size), 14f, true)
        task.contexts.forEach(::renderContext)
    }

    private fun renderContext(context: HandoffContext) {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 16, 24, 16)
        }
        addCardText(card, context.state.title, 16f, true)
        addCardText(card, context.state.domain, 14f, false)
        addCardText(card, context.reconstructionTarget, 12f, false)
        addCardText(
            card,
            getString(
                R.string.context_details,
                context.contextId,
                context.reconstructionMethod,
                context.sufficiencyScore
            ),
            12f,
            false
        )
        addOpenAction(card, context)
        activityContent.addView(card)
    }

    private fun addOpenAction(parent: LinearLayout, context: HandoffContext) {
        val openButton = Button(this).apply {
            text = getString(R.string.open_context)
            setOnClickListener {
                when (val result = urlReconstructor.open(context)) {
                    UrlReconstructor.OpenResult.Opened -> {
                        statusText.setText(R.string.browser_opened)
                    }
                    UrlReconstructor.OpenResult.InvalidUrl -> {
                        statusText.setText(R.string.invalid_context_url)
                    }
                    UrlReconstructor.OpenResult.NoBrowser -> {
                        statusText.setText(R.string.no_browser_available)
                    }
                    is UrlReconstructor.OpenResult.NotSupported -> {
                        statusText.text = getString(
                            R.string.reconstruction_not_supported,
                            result.method
                        )
                    }
                }
            }
        }

        val supportedMethod = context.reconstructionMethod in SUPPORTED_METHODS
        val validUrl = isHttpUrl(context.reconstructionTarget)
        when {
            supportedMethod && validUrl -> {
                parent.addView(openButton)
            }
            !supportedMethod -> {
                addCardText(
                    parent,
                    getString(
                        R.string.reconstruction_not_supported,
                        context.reconstructionMethod
                    ),
                    12f,
                    false
                )
            }
            else -> {
                addCardText(parent, getString(R.string.invalid_context_url), 12f, false)
            }
        }
    }

    private fun isHttpUrl(target: String): Boolean {
        val uri = android.net.Uri.parse(target)
        return uri.scheme in HTTP_SCHEMES && !uri.host.isNullOrBlank()
    }

    private fun addText(value: String, size: Float, bold: Boolean) {
        val textView = TextView(this).apply {
            text = value
            textSize = size
            setPadding(0, 12, 0, 6)
            if (bold) {
                setTypeface(typeface, android.graphics.Typeface.BOLD)
            }
        }
        activityContent.addView(textView)
    }

    private fun addCardText(
        parent: LinearLayout,
        value: String,
        size: Float,
        bold: Boolean
    ) {
        val textView = TextView(this).apply {
            text = value
            textSize = size
            setPadding(0, 4, 0, 4)
            if (bold) {
                setTypeface(typeface, android.graphics.Typeface.BOLD)
            }
        }
        parent.addView(textView)
    }

    private companion object {
        const val SAMPLE_FILE = "activity_handoff.json"
        const val REQUEST_OPEN_JSON = 1001
        val HTTP_SCHEMES = setOf("http", "https")
        val SUPPORTED_METHODS = setOf(
            "url",
            "url_with_metadata",
            "url_with_content"
        )
    }
}
