package com.taskflow.mobile

import android.app.Activity
import android.app.AlertDialog
import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.text.LineBreaker
import android.text.InputType
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.taskflow.mobile.data.HandoffClient
import com.taskflow.mobile.data.HandoffParser
import com.taskflow.mobile.model.ActivityHandoff
import com.taskflow.mobile.model.HandoffContext
import com.taskflow.mobile.model.TaskHandoff
import com.taskflow.mobile.model.UnifiedActivityHandoff
import com.taskflow.mobile.reconstruction.UrlReconstructor
import java.io.IOException
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.Future
import kotlin.math.roundToInt

class MainActivity : Activity() {
    private lateinit var statusText: TextView
    private lateinit var activityContent: LinearLayout
    private lateinit var activityScrollView: ScrollView
    private lateinit var urlReconstructor: UrlReconstructor
    private lateinit var receiveHandoffButton: Button
    private val mainHandler = Handler(Looper.getMainLooper())
    private val receiveExecutor = Executors.newSingleThreadExecutor()
    @Volatile private var isReceiving = false
    private var receiveFuture: Future<*>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        activityContent = findViewById(R.id.activityContent)
        activityScrollView = findViewById(R.id.activityScrollView)
        urlReconstructor = UrlReconstructor(this)
        findViewById<Button>(R.id.loadSampleButton).setOnClickListener {
            cancelReceiveLoop()
            loadSamplePackage()
        }
        findViewById<Button>(R.id.importJsonButton).setOnClickListener {
            cancelReceiveLoop()
            openJsonDocument()
        }
        findViewById<Button>(R.id.connectionSettingsButton).setOnClickListener {
            showConnectionSettings()
        }
        receiveHandoffButton = findViewById(R.id.receiveHandoffButton)
        receiveHandoffButton.setOnClickListener {
            if (isReceiving) {
                cancelReceiveLoop(showStatus = true)
            } else {
                startReceiveLoop()
            }
        }
        loadSamplePackage()
    }

    override fun onDestroy() {
        cancelReceiveLoop()
        receiveExecutor.shutdownNow()
        super.onDestroy()
    }

    private fun loadSamplePackage() {
        statusText.setText(R.string.loading_package)
        activityContent.removeAllViews()
        activityScrollView.scrollTo(0, 0)

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
        cancelReceiveLoop()
        statusText.setText(R.string.importing_package)
        activityContent.removeAllViews()
        activityScrollView.scrollTo(0, 0)

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

    private fun showConnectionSettings() {
        val preferences = getSharedPreferences(CONNECTION_PREFERENCES, MODE_PRIVATE)
        val serverInput = EditText(this).apply {
            hint = getString(R.string.server_address_hint)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
            setText(preferences.getString(SERVER_URL_KEY, ""))
        }
        val tokenInput = EditText(this).apply {
            hint = getString(R.string.pairing_token_hint)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            setSingleLine(true)
            setText(preferences.getString(PAIRING_TOKEN_KEY, ""))
        }
        val fields = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(8), dp(20), 0)
            addView(serverInput)
            addView(tokenInput)
        }

        AlertDialog.Builder(this)
            .setTitle(R.string.connection_settings_title)
            .setView(fields)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.save_connection) { _, _ ->
                val serverUrl = serverInput.text.toString().trim().trimEnd('/')
                val pairingToken = tokenInput.text.toString().trim()
                if (!isValidServerUrl(serverUrl)) {
                    statusText.setText(R.string.invalid_server_address)
                } else if (pairingToken.isEmpty()) {
                    statusText.setText(R.string.connection_required)
                } else {
                    preferences.edit()
                        .putString(SERVER_URL_KEY, serverUrl)
                        .putString(PAIRING_TOKEN_KEY, pairingToken)
                        .apply()
                    statusText.setText(R.string.connection_saved)
                }
            }
            .show()
    }

    private fun isValidServerUrl(value: String): Boolean {
        val uri = Uri.parse(value)
        if (uri.scheme !in HTTP_SCHEMES || uri.host.isNullOrBlank()) return false
        if (!uri.path.isNullOrEmpty() && uri.path != "/") return false
        if (!uri.query.isNullOrEmpty() || !uri.fragment.isNullOrEmpty()) return false
        if (uri.userInfo != null) return false

        if (uri.scheme == "http") {
            val host = uri.host?.lowercase() ?: return false
            if (host == "localhost") return true
            val octets = host.split(".").map { it.toIntOrNull() ?: return false }
            if (octets.size != 4 || octets.any { it !in 0..255 }) return false
            val first = octets[0]
            val second = octets[1]
            return first == 10 ||
                first == 127 ||
                (first == 192 && second == 168) ||
                (first == 172 && second in 16..31)
        }
        return true
    }

    private fun startReceiveLoop() {
        val preferences = getSharedPreferences(CONNECTION_PREFERENCES, MODE_PRIVATE)
        val serverUrl = preferences.getString(SERVER_URL_KEY, "")?.trim().orEmpty()
        val pairingToken = preferences.getString(PAIRING_TOKEN_KEY, "")?.trim().orEmpty()
        if (!isValidServerUrl(serverUrl) || pairingToken.isEmpty()) {
            statusText.setText(R.string.connection_required)
            showConnectionSettings()
            return
        }

        val deviceId = preferences.getString(DEVICE_ID_KEY, null)
            ?: UUID.randomUUID().toString().also {
                preferences.edit().putString(DEVICE_ID_KEY, it).apply()
            }
        val client = HandoffClient(serverUrl, pairingToken)
        isReceiving = true
        receiveHandoffButton.setText(R.string.stop_receiving)
        statusText.setText(R.string.connecting_to_server)

        receiveFuture = receiveExecutor.submit {
            try {
                client.register(
                    deviceId = deviceId,
                    deviceName = "TaskFlow Android App",
                    userAgent = "Android ${android.os.Build.VERSION.RELEASE}; ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}"
                )
                updateStatusIfReceiving(R.string.waiting_for_handoff)

                while (isReceiving && !Thread.currentThread().isInterrupted) {
                    val pending = client.receiveNext(deviceId)
                    if (pending != null) {
                        if (!isReceiving) return@submit
                        val parsedResult = HandoffParser().parse(pending.document.toString())
                        var acknowledgementError: String? = null
                        try {
                            client.acknowledge(deviceId, pending.handoffId)
                        } catch (error: Exception) {
                            acknowledgementError = error.message
                        }

                        mainHandler.post {
                            if (isFinishing || isDestroyed) return@post
                            isReceiving = false
                            receiveFuture = null
                            receiveHandoffButton.setText(R.string.receive_handoff)
                            if (parsedResult.isSuccess) {
                                activityContent.removeAllViews()
                                activityScrollView.scrollTo(0, 0)
                                displayResult(parsedResult, R.string.import_error)
                                statusText.setText(R.string.handoff_received)
                                if (acknowledgementError != null) {
                                    statusText.text = getString(
                                        R.string.handoff_ack_error,
                                        acknowledgementError
                                    )
                                }
                            } else {
                                statusText.text = getString(
                                    R.string.malformed_handoff,
                                    parsedResult.exceptionOrNull()?.message
                                        ?: getString(R.string.unknown_error)
                                )
                            }
                        }
                        return@submit
                    }
                    Thread.sleep(POLL_INTERVAL_MS)
                }
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
            } catch (error: Exception) {
                mainHandler.post {
                    if (!isFinishing && !isDestroyed && isReceiving) {
                        isReceiving = false
                        receiveFuture = null
                        receiveHandoffButton.setText(R.string.receive_handoff)
                        statusText.text = getString(
                            R.string.handoff_receive_error,
                            error.message ?: getString(R.string.unknown_error)
                        )
                    }
                }
            }
        }
    }

    private fun updateStatusIfReceiving(stringId: Int) {
        mainHandler.post {
            if (!isFinishing && !isDestroyed && isReceiving) {
                statusText.setText(stringId)
            }
        }
    }

    private fun cancelReceiveLoop(showStatus: Boolean = false) {
        val wasReceiving = isReceiving
        isReceiving = false
        receiveFuture?.cancel(true)
        receiveFuture = null
        if (::receiveHandoffButton.isInitialized) {
            receiveHandoffButton.setText(R.string.receive_handoff)
        }
        if (showStatus && wasReceiving && ::statusText.isInitialized) {
            statusText.setText(R.string.handoff_receive_cancelled)
        }
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
                activityScrollView.post {
                    activityScrollView.scrollTo(0, 0)
                }
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

    @SuppressLint("InlinedApi") // The simple strategy is inlined; setBreakStrategy is available since API 23.
    private fun cardText(value: String, size: Float, bold: Boolean): TextView {
        return TextView(this).apply {
            text = value
            textSize = size
            setTextColor(getColor(R.color.on_surface))
            setPadding(0, dp(3), 0, dp(5))
            setLineSpacing(0f, 1.12f)
            isSingleLine = false
            setHorizontallyScrolling(false)
            breakStrategy = LineBreaker.BREAK_STRATEGY_SIMPLE
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
        const val CONNECTION_PREFERENCES = "taskflow_mobile_connection"
        const val SERVER_URL_KEY = "server_url"
        const val PAIRING_TOKEN_KEY = "pairing_token"
        const val DEVICE_ID_KEY = "device_id"
        const val POLL_INTERVAL_MS = 2000L
        val HTTP_SCHEMES = setOf("http", "https")
        val SUPPORTED_METHODS = setOf(
            "url",
            "url_with_metadata",
            "url_with_content"
        )
    }
}
