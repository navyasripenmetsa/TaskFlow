import json

from task_engine.embeddings import EmbeddingEngine
from task_engine.handoff import HandoffBuilder
from task_engine.normalizer import load_contexts
from task_engine.reconstruction import ReconstructionEngine
from task_engine.similarity import ContextSimilarityEngine
from task_engine.state_selector import StateSelector
from task_engine.task_inference import TaskInferenceEngine


with open(
    "data/test_session.json",
    "r",
    encoding="utf-8",
) as file:
    session_data = json.load(file)


contexts = load_contexts(session_data)

embedding_engine = EmbeddingEngine()

similarity_engine = ContextSimilarityEngine(
    embedding_engine
)

task_engine = TaskInferenceEngine(
    embedding_engine,
    similarity_engine,
)

tasks = task_engine.discover_tasks(
    contexts
)

selector = StateSelector()

handoff_builder = HandoffBuilder()

reconstruction_engine = (
    ReconstructionEngine()
)


print()
print("HANDOFF RECONSTRUCTION TEST")
print("===========================")


for task in tasks[:1]:

    task_contexts = [
        context
        for context in contexts
        if context.context_id
        in task.context_ids
    ]

    selected_states = (
        selector.select_for_task(
            task_contexts
        )
    )

    package = handoff_builder.build(
        task,
        selected_states,
    )

    print()
    print(f"Task: {package.task_id}")
    print(f"Label: {package.task_label}")

    for handoff_state in package.contexts:

        result = (
            reconstruction_engine.reconstruct(
                handoff_state
            )
        )

        print()
        print(
            f"{handoff_state.context_id}"
        )

        print(
            f"  method: "
            f"{result['method']}"
        )

        print(
            f"  success: "
            f"{result['success']}"
        )

        print(
            f"  action: "
            f"{result['action']}"
        )

        print(
            f"  target: "
            f"{result['target']}"
        )