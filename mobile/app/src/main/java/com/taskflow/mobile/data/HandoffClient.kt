package com.taskflow.mobile.data

import android.net.Uri
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

data class PendingHandoff(
    val handoffId: String,
    val document: JSONObject
)

class HandoffClient(
    private val serverUrl: String,
    private val pairingToken: String
) {
    fun register(deviceId: String, deviceName: String, userAgent: String) {
        val body = JSONObject()
            .put("device_id", deviceId)
            .put("device_name", deviceName)
            .put("user_agent", userAgent)
        request("/devices/register", "POST", body.toString())
    }

    fun receiveNext(deviceId: String): PendingHandoff? {
        val response = request(
            "/devices/${Uri.encode(deviceId)}/handoffs/next",
            "GET"
        )
        if (response.statusCode == HttpURLConnection.HTTP_NO_CONTENT) {
            return null
        }

        val result = JSONObject(response.body)
        val handoffId = result.optString("handoff_id").trim()
        val document = result.optJSONObject("document")
        if (handoffId.isEmpty() || document == null) {
            throw IOException("The laptop returned an incomplete handoff.")
        }
        return PendingHandoff(handoffId, document)
    }

    fun acknowledge(deviceId: String, handoffId: String) {
        request(
            "/devices/${Uri.encode(deviceId)}/handoffs/${Uri.encode(handoffId)}/ack",
            "POST"
        )
    }

    private fun request(
        path: String,
        method: String,
        body: String? = null
    ): ApiResponse {
        val connection = URL("${serverUrl.trimEnd('/')}$path")
            .openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = REQUEST_TIMEOUT_MS
            connection.readTimeout = REQUEST_TIMEOUT_MS
            connection.useCaches = false
            connection.setRequestProperty("X-Taskflow-Token", pairingToken)
            connection.setRequestProperty("Accept", "application/json")
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { output ->
                    output.write(body.toByteArray(Charsets.UTF_8))
                }
            }

            val statusCode = connection.responseCode
            val stream = if (statusCode in 200..299) {
                connection.inputStream
            } else {
                connection.errorStream
            }
            val responseBody = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }
                .orEmpty()

            if (statusCode !in 200..299) {
                val detail = runCatching {
                    JSONObject(responseBody).optString("detail")
                }.getOrNull()?.takeIf(String::isNotBlank)
                throw IOException(detail ?: "Laptop server returned HTTP $statusCode.")
            }
            return ApiResponse(statusCode, responseBody)
        } finally {
            connection.disconnect()
        }
    }

    private data class ApiResponse(
        val statusCode: Int,
        val body: String
    )

    private companion object {
        const val REQUEST_TIMEOUT_MS = 5_000
    }
}
