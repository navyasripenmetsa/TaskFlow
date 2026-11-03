import json
from pathlib import Path
from backend.task_engine.embeddings import EmbeddingEngine
from backend.task_engine.similarity import ContextSimilarityEngine
from backend.task_engine.normalizer import load_contexts
from backend.task_engine.task_inference import TaskInferenceEngine
from backend.task_engine.state_selector import StateSelector
from backend.task_engine.handoff import HandoffBuilder
from backend.task_engine.google_sheets_adapter import GoogleSheetsAdapter
# Initialize shared engines once
embedding_engine = EmbeddingEngine()
similarity_engine = ContextSimilarityEngine(
    embedding_engine=embedding_engine
)
# --------------------------------------------------
# Load source contexts
# --------------------------------------------------

project_root = Path(__file__).resolve().parent

session_path = project_root / "data" / "real_session.json"

with open(session_path, "r", encoding="utf-8") as file:
    session_data = json.load(file)

contexts = load_contexts(session_data)
# Enrich existing Google Sheets contexts through the Sheets API
sheets_adapter = GoogleSheetsAdapter()

for context in contexts:
    spreadsheet_id = sheets_adapter.extract_spreadsheet_id(context.url)

    if spreadsheet_id:
        print(f"\nReading spreadsheet context: {context.context_id}")

        spreadsheet_data = sheets_adapter.extract(context.url)

        if spreadsheet_data:
            context.interaction_state["spreadsheet_data"] = spreadsheet_data

            # Add spreadsheet values to the existing context's semantic text
            spreadsheet_text = []

            for sheet in spreadsheet_data["sheets"]:
                spreadsheet_text.append(
                    f"Sheet: {sheet['sheet_name']}"
                )

                for row in sheet["values"]:
                    spreadsheet_text.append(
                        " | ".join(str(cell) for cell in row)
                    )

            context.text += "\n" + "\n".join(spreadsheet_text)

            print(
                f"Enriched {context.context_id} with "
                f"{len(spreadsheet_data['sheets'])} sheets"
            )
print("\nSPREADSHEET CONTEXT DIAGNOSTIC")

for context in contexts:
    if context.context_id == "ctx_005":
        print("Title:", context.title)
        print("URL:", context.url)
        print("Domain:", context.domain)
        print("Text:", repr(context.text[:2000]))
        print("Interaction state:", context.interaction_state)

print(f"\nLoaded {len(contexts)} contexts")


# --------------------------------------------------
# Discover tasks dynamically
# --------------------------------------------------

task_inference_engine = TaskInferenceEngine(
    embedding_engine=embedding_engine,
    similarity_engine=similarity_engine
)
# TEMPORARY: Inspect context similarity scores

similarity_matrix = similarity_engine.build_similarity_matrix(contexts)
print("\nCONTEXT RELATIONSHIP DIAGNOSTIC")

for context in contexts:
    print(
        context.context_id,
        "|",
        context.title,
        "|",
        "text length:",
        len(context.text),
        "|",
        "spreadsheet:",
        "spreadsheet_data" in context.interaction_state
    )

print("\nPAIRWISE SIMILARITY SCORES")
print("\nFULL SIMILARITY MATRIX")

print("     ", end="")

for context in contexts:
    print(f"{context.context_id:>9}", end="")

print()

for i, context in enumerate(contexts):
    print(f"{context.context_id:>6}", end="")

    for j in range(len(contexts)):
        print(f"{similarity_matrix[i, j]:9.3f}", end="")

    print()


for i, context_a in enumerate(contexts):
    for j, context_b in enumerate(contexts):

        if j <= i:
            continue

        if (
            context_a.context_id == "ctx_005"
            or context_b.context_id == "ctx_005"
        ):
            print(
                f"{context_a.context_id} - {context_b.context_id}: "
                f"{similarity_matrix[i, j]:.3f}"
            )
tasks = task_inference_engine.discover_tasks(contexts)

print(f"\nDiscovered {len(tasks)} tasks")

for task in tasks:
    print(f"\nTask: {task.label}")
    print(f"Task ID: {task.task_id}")
    print(f"Contexts: {task.context_ids}")

# --------------------------------------------------
# Select sufficient state representations
# --------------------------------------------------

state_selector = StateSelector()

print("\nSTATE REPRESENTATION SELECTION")

task_context_map = {
    context.context_id: context
    for context in contexts
}

task_state_results = {}

for task in tasks:

    task_contexts = [
        task_context_map[context_id]
        for context_id in task.context_ids
        if context_id in task_context_map
    ]

    report = state_selector.select_for_task_with_report(
        task_contexts
    )

    task_state_results[task.task_id] = report

    print(f"\nTask: {task.label}")
    print("Contexts:", report["context_count"])
    print("Selected states:", report["selected_state_count"])
    print("Failed contexts:", report["failed_context_ids"])
    print("Transfer cost:", report["total_cost"])


# ---------------------------------------------------------
# BUILD TASK HANDOFF PACKAGES
# ---------------------------------------------------------

print("\nHANDOFF PACKAGE GENERATION")

handoff_builder = HandoffBuilder()

handoff_packages = []

for task in tasks:

    report = task_state_results[task.task_id]

    selected_states = report["selected_states"]

    package = handoff_builder.build(
        task=task,
        selected_states=selected_states,
    )

    expected_context_ids = set(task.context_ids)

    packaged_context_ids = {
        state.context_id
        for state in package.contexts
    }

    missing_contexts = (
        expected_context_ids - packaged_context_ids
    )

    handoff_packages.append(package)

    print(f"\nTask: {package.task_label}")
    print(f"Task ID: {package.task_id}")
    print(f"Expected contexts: {len(expected_context_ids)}")
    print(f"Packaged contexts: {len(packaged_context_ids)}")
    print(f"Missing contexts: {sorted(missing_contexts)}")
    print(f"Transfer cost: {sum(s.cost for s in package.contexts)}")

print("\nHANDOFF SUMMARY")
print("Total tasks:", len(handoff_packages))
print(
    "Total packaged contexts:",
    sum(len(package.contexts) for package in handoff_packages)
)
