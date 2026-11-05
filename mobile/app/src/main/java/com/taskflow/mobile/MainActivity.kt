package com.taskflow.mobile

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.text.Layout
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
import kotlin.math.roundToInt

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
        val activityCard = createCard(R.color.activity_accent).apply {
            addView(sectionLabel(R.string.activity_section, R.color.activity_accent))
            addView(cardText(activity.activityLabel, 22f, true))
            addView(cardText(getString(R.string.activity_id, activity.activityId), 13f, false))
        }

        activity.handoffPackages.forEach { task ->
            renderTask(task, activityCard)
        }
        activity.activityHandoffPackage?.let { renderUnifiedActivity(it, activityCard) }
        activityContent.addView(activityCard, childLayoutParams(0))
    }

    private fun renderUnifiedActivity(
        activityPackage: UnifiedActivityHandoff,
        parent: LinearLayout
    ) {
        val packageCard = createCard(R.color.task_accent).apply {
            addView(sectionLabel(R.string.task_section, R.color.task_accent))
            addView(cardText(activityPackage.activityLabel, 19f, true))
            addView(cardText(activityPackage.activityDescription, 14f, false))
            addView(cardText(
            getString(R.string.activity_context_count, activityPackage.contexts.size),
            14f,
            true
            ))
        }
        activityPackage.contexts.forEach { context ->
            renderContext(context, packageCard)
        }
        parent.addView(packageCard, childLayoutParams())
    }

    private fun renderTask(task: TaskHandoff, parent: LinearLayout) {
        val taskCard = createCard(R.color.task_accent).apply {
            addView(sectionLabel(R.string.task_section, R.color.task_accent))
            addView(cardText(task.taskLabel, 19f, true))
            addView(cardText(task.taskDescription, 14f, false))
            addView(cardText(getString(R.string.context_count, task.contexts.size), 14f, true))
        }
        task.contexts.forEach { context ->
            renderContext(context, taskCard)
        }
        parent.addView(taskCard, childLayoutParams())
    }

    private fun renderContext(context: HandoffContext, parent: LinearLayout) {
        val card = createCard(R.color.context_accent).apply {
            addView(sectionLabel(R.string.context_section, R.color.context_accent))
            addView(cardText(context.state.title, 16f, true))
            addView(cardText(context.state.domain, 14f, false))
            addView(cardText(context.reconstructionTarget, 12f, false).apply {
                setTextIsSelectable(true)
            })
            addView(cardText(
                getString(
                    R.string.context_details,
                    context.contextId,
                    context.reconstructionMethod,
                    context.sufficiencyScore
                ),
                12f,
                false
            ))
        }
        addOpenAction(card, context)
        parent.addView(card, childLayoutParams(8))
    }

    private fun addOpenAction(parent: LinearLayout, context: HandoffContext) {
        val openButton = Button(this).apply {
            backgroundTintList = android.content.res.ColorStateList.valueOf(
                getColor(R.color.primary)
            )
            setTextColor(getColor(R.color.on_primary))
            minHeight = dp(48)
            isAllCaps = false
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
                parent.addView(cardText(
                    getString(
                        R.string.reconstruction_not_supported,
                        context.reconstructionMethod
                    ),
                    12f,
                    false
                ))
            }
            else -> {
                parent.addView(cardText(getString(R.string.invalid_context_url), 12f, false))
            }
        }
    }

    private fun isHttpUrl(target: String): Boolean {
        val uri = android.net.Uri.parse(target)
        return uri.scheme in HTTP_SCHEMES && !uri.host.isNullOrBlank()
    }

    private fun createCard(accentColor: Int): LinearLayout {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(16))
            background = GradientDrawable().apply {
                setColor(getColor(R.color.surface_card))
                cornerRadius = dp(12).toFloat()
                setStroke(dp(1), getColor(accentColor))
            }
        }
    }

    private fun sectionLabel(stringId: Int, colorId: Int): TextView {
        return TextView(this).apply {
            text = getString(stringId)
            textSize = 11f
            setTextColor(getColor(colorId))
            setTypeface(typeface, Typeface.BOLD)
            letterSpacing = 0.12f
            setPadding(0, 0, 0, dp(6))
        }
    }

    private fun cardText(value: String, size: Float, bold: Boolean): TextView {
        return TextView(this).apply {
            text = value
            textSize = size
            setTextColor(getColor(R.color.on_surface))
            setPadding(0, dp(3), 0, dp(5))
            setLineSpacing(0f, 1.12f)
            isSingleLine = false
            setHorizontallyScrolling(false)
            breakStrategy = Layout.BREAK_STRATEGY_SIMPLE
            ellipsize = null
            if (bold) {
                setTypeface(typeface, Typeface.BOLD)
            }
        }
    }

    private fun childLayoutParams(topMargin: Int = 12): LinearLayout.LayoutParams {
        return LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply {
            setMargins(0, dp(topMargin), 0, 0)
        }
    }

    private fun dp(value: Int): Int {
        return (value * resources.displayMetrics.density).roundToInt()
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
