package com.taskflow.mobile

import android.app.Activity
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.taskflow.mobile.data.HandoffParser
import com.taskflow.mobile.model.ActivityHandoff
import com.taskflow.mobile.model.HandoffContext
import com.taskflow.mobile.model.TaskHandoff

class MainActivity : Activity() {
    private lateinit var statusText: TextView
    private lateinit var activityContent: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        activityContent = findViewById(R.id.activityContent)
        findViewById<Button>(R.id.loadSampleButton).setOnClickListener {
            loadSamplePackage()
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
                    R.string.package_error,
                    error.message ?: getString(R.string.unknown_error)
                )
            }
    }

    private fun renderActivity(activity: ActivityHandoff) {
        addText(activity.activityLabel, 24f, true)
        addText(getString(R.string.activity_id, activity.activityId), 14f, false)

        activity.handoffPackages.forEach(::renderTask)
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
        activityContent.addView(card)
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
    }
}
