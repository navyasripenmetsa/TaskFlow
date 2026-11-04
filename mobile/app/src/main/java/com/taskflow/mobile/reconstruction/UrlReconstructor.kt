package com.taskflow.mobile.reconstruction

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import com.taskflow.mobile.model.HandoffContext

class UrlReconstructor(
    private val context: Context
) {
    fun open(contextItem: HandoffContext): OpenResult {
        if (contextItem.reconstructionMethod !in SUPPORTED_METHODS) {
            return OpenResult.NotSupported(contextItem.reconstructionMethod)
        }

        val uri = Uri.parse(contextItem.reconstructionTarget)
        if (uri.scheme !in HTTP_SCHEMES || uri.host.isNullOrBlank()) {
            return OpenResult.InvalidUrl
        }

        val intent = Intent(Intent.ACTION_VIEW, uri)
        if (intent.resolveActivity(context.packageManager) == null) {
            return OpenResult.NoBrowser
        }

        return try {
            context.startActivity(intent)
            OpenResult.Opened
        } catch (_: ActivityNotFoundException) {
            OpenResult.NoBrowser
        } catch (_: SecurityException) {
            OpenResult.NoBrowser
        }
    }

    sealed interface OpenResult {
        data object Opened : OpenResult
        data object InvalidUrl : OpenResult
        data object NoBrowser : OpenResult
        data class NotSupported(val method: String) : OpenResult
    }

    private companion object {
        val HTTP_SCHEMES = setOf("http", "https")
        val SUPPORTED_METHODS = setOf(
            "url",
            "url_with_metadata",
            "url_with_content"
        )
    }
}
