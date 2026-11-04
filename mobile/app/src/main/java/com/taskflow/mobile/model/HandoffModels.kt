package com.taskflow.mobile.model

data class HandoffDocument(
    val activities: List<ActivityHandoff>
)

data class ActivityHandoff(
    val activityId: String,
    val activityLabel: String,
    val handoffPackages: List<TaskHandoff>,
    val activityHandoffPackage: UnifiedActivityHandoff?
)

data class TaskHandoff(
    val taskId: String,
    val taskLabel: String,
    val taskDescription: String,
    val contexts: List<HandoffContext>
)

data class UnifiedActivityHandoff(
    val activityId: String,
    val activityLabel: String,
    val activityDescription: String,
    val taskIds: List<String>,
    val contexts: List<HandoffContext>
)

data class HandoffContext(
    val contextId: String,
    val representationId: String,
    val reconstructionMethod: String,
    val reconstructionTarget: String,
    val state: ContextState,
    val cost: Double,
    val sufficiencyScore: Double
)

data class ContextState(
    val url: String,
    val title: String,
    val domain: String
)
