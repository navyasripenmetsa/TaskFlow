package com.taskflow.mobile.data

import com.taskflow.mobile.model.ActivityHandoff
import com.taskflow.mobile.model.ContextState
import com.taskflow.mobile.model.HandoffContext
import com.taskflow.mobile.model.HandoffDocument
import com.taskflow.mobile.model.TaskHandoff
import com.taskflow.mobile.model.UnifiedActivityHandoff
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

class HandoffParser {
    fun parse(json: String): Result<HandoffDocument> = runCatching {
        val root = JSONObject(json)
        val activities = root.requiredArray("activities")
        require(activities.length() > 0) { "The package must contain at least one activity." }

        HandoffDocument(
            activities = (0 until activities.length()).map { index ->
                parseActivity(activities.requiredObject(index))
            }
        )
    }.recoverCatching { error ->
        throw HandoffParseException(error.message ?: "The handoff package is invalid.", error)
    }

    private fun parseActivity(json: JSONObject): ActivityHandoff {
        val packages = json.requiredArray("handoff_packages")
        return ActivityHandoff(
            activityId = json.requiredString("activity_id"),
            activityLabel = json.requiredString("activity_label"),
            handoffPackages = (0 until packages.length()).map { index ->
                parseTask(packages.requiredObject(index))
            },
            activityHandoffPackage = json.optJSONObject("activity_handoff_package")
                ?.let(::parseUnifiedActivity)
        )
    }

    private fun parseTask(json: JSONObject): TaskHandoff {
        val contexts = json.requiredArray("contexts")
        return TaskHandoff(
            taskId = json.requiredString("task_id"),
            taskLabel = json.requiredString("task_label"),
            taskDescription = json.requiredString("task_description"),
            contexts = (0 until contexts.length()).map { index ->
                parseContext(contexts.requiredObject(index))
            }
        )
    }

    private fun parseUnifiedActivity(json: JSONObject): UnifiedActivityHandoff {
        val taskIds = json.requiredArray("task_ids")
        val contexts = json.requiredArray("contexts")
        return UnifiedActivityHandoff(
            activityId = json.requiredString("activity_id"),
            activityLabel = json.requiredString("activity_label"),
            activityDescription = json.requiredString("activity_description"),
            taskIds = (0 until taskIds.length()).map { index ->
                taskIds.requiredString(index)
            },
            contexts = (0 until contexts.length()).map { index ->
                parseContext(contexts.requiredObject(index))
            }
        )
    }

    private fun parseContext(json: JSONObject): HandoffContext {
        val state = json.requiredObject("state")
        return HandoffContext(
            contextId = json.requiredString("context_id"),
            representationId = json.requiredString("representation_id"),
            reconstructionMethod = json.requiredString("reconstruction_method"),
            reconstructionTarget = json.requiredString("reconstruction_target"),
            state = ContextState(
                url = state.requiredString("url"),
                title = state.requiredString("title"),
                domain = state.requiredString("domain")
            ),
            cost = json.requiredDouble("cost"),
            sufficiencyScore = json.requiredDouble("sufficiency_score")
        )
    }
}

class HandoffParseException(message: String, cause: Throwable) : Exception(message, cause)

private fun JSONObject.requiredString(name: String): String {
    val value = opt(name)
    if (value !is String) {
        throw JSONException("Missing required field '$name'.")
    }
    if (value.isBlank()) {
        throw JSONException("Required field '$name' must not be blank.")
    }
    return value
}

private fun JSONObject.requiredArray(name: String): JSONArray =
    optJSONArray(name) ?: throw JSONException("Missing required array '$name'.")

private fun JSONObject.requiredObject(name: String): JSONObject =
    optJSONObject(name) ?: throw JSONException("Missing required object '$name'.")

private fun JSONObject.requiredDouble(name: String): Double {
    val value = opt(name)
    if (value !is Number) {
        throw JSONException("Missing required numeric field '$name'.")
    }
    val number = value.toDouble()
    if (!number.isFinite()) {
        throw JSONException("Field '$name' must be finite.")
    }
    return number
}

private fun JSONArray.requiredObject(index: Int): JSONObject =
    optJSONObject(index) ?: throw JSONException("Array item $index must be an object.")

private fun JSONArray.requiredString(index: Int): String {
    val value = opt(index)
    if (value !is String) {
        throw JSONException("Array item $index must be a string.")
    }
    if (value.isBlank()) {
        throw JSONException("Array item $index must be a non-blank string.")
    }
    return value
}
