import json
from backend.task_engine.normalizer import load_contexts
from backend.task_engine.embeddings import EmbeddingEngine
from backend.task_engine.task_inference import TaskInferenceEngine
from backend.task_engine.activity_inference import ActivityInferenceEngine
from backend.task_engine.state_selector import StateSelector
from backend.task_engine.handoff import HandoffBuilder
from backend.task_engine.reconstruction import ReconstructionEngine

# Load the real captured browser session.
with open("data/real_session.json", "r", encoding="utf-8") as file:
    session_data = json.load(file)

contexts = load_contexts(session_data)

print("Loaded contexts:", len(contexts))


# Discover individual tasks.
embedding_engine = EmbeddingEngine()

task_engine = TaskInferenceEngine(
    embedding_engine=embedding_engine
)

tasks = task_engine.discover_tasks(contexts)

print("\nDISCOVERED TASKS:", len(tasks))

for task in tasks:
    print("\nTask:", task.label)
    print("Task ID:", task.task_id)
    print("Contexts:", task.context_ids)


# Discover broader activities.
activity_engine = ActivityInferenceEngine(
    embedding_engine=embedding_engine
)

activities = activity_engine.discover_activities(tasks,contexts=contexts,)

print("\nDISCOVERED ACTIVITIES:", len(activities))

for activity in activities:
    print("\nActivity:", activity.label)
    print("Goal:", activity.description)
    print("Task IDs:", activity.task_ids)
    print("Context IDs:", activity.context_ids)
    print("Coherence:", round(activity.coherence, 3))

# Test minimum-context state selection and handoff generation.

state_selector = StateSelector()
export_data = {
    "activities": []
}
handoff_builder = HandoffBuilder()

for activity in activities:

    print(f"\n{'=' * 50}")
    print("HANDOFF ACTIVITY:", activity.label)
    activity_export = {
        "activity_id": activity.activity_id,
        "activity_label": activity.label,
        "handoff_packages": [],
        "activity_handoff_package": None,
    }
    activity_selected_states = []
    for task_id in activity.task_ids:

        # Find the corresponding individual task.
        task = next(
            task for task in tasks
            if task.task_id == task_id
        )

        print("\nTASK:", task.label)

        # Get contexts belonging to this task.
        task_contexts = [
            context for context in contexts
            if context.context_id in task.context_ids
        ]

        # Select minimum sufficient state.
        selection_report = (
            state_selector.select_for_task_with_report(
                task_contexts
            )
        )
        activity_selected_states.extend(
            selection_report["selected_states"]
        )
        print(
            "Selected states:",
            selection_report["selected_state_count"]
        )
        print(
            "Total cost:",
            selection_report["total_cost"]
        )
        print(
            "Failed contexts:",
            selection_report["failed_context_ids"]
        )

        # Build handoff package for this task.
        handoff_package = handoff_builder.build(
            task,
            selection_report["selected_states"]
        )
        activity_export["handoff_packages"].append(
            handoff_package.to_dict()
        )

        print("\nHANDOFF PACKAGE:")
        print(
            json.dumps(
                handoff_package.to_dict(),
                indent=2,
                ensure_ascii=False
            )
        )
        # Test reconstruction of each selected handoff state.
        reconstruction_engine = ReconstructionEngine()

        print("\nRECONSTRUCTION RESULTS:")

        for handoff_state in handoff_package.contexts:
            result = reconstruction_engine.reconstruct(
                handoff_state
            )

            print(json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            ))
        # Build one unified handoff package for the entire activity.
    activity_package = handoff_builder.build_activity(
        activity,
        activity_selected_states,
    )

    activity_export["activity_handoff_package"] = (
        activity_package.to_dict()
    )

    print("\nUNIFIED ACTIVITY HANDOFF PACKAGE:")
    print(
        json.dumps(
            activity_package.to_dict(),
            indent=2,
            ensure_ascii=False,
        )
    )        
    export_data["activities"].append(activity_export)
# Verify that no contexts were lost or duplicated.
assigned_contexts = [
    context_id
    for activity in activities
    for context_id in activity.context_ids
]

expected_contexts = {
    context.context_id for context in contexts
}

print("\nCONTEXT VERIFICATION")
print("Expected:", len(expected_contexts))
print("Assigned:", len(assigned_contexts))
print("Unique:", len(set(assigned_contexts)))
print("Missing:", expected_contexts - set(assigned_contexts))
print("Duplicates:", len(assigned_contexts) - len(set(assigned_contexts)))
with open("data/activity_handoff.json", "w", encoding="utf-8") as file:
    json.dump(export_data, file, indent=2, ensure_ascii=False)
print("\nHandoff export saved to data/activity_handoff.json")