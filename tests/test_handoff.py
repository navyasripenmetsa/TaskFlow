import json

from task_engine.normalizer import load_contexts
from task_engine.embeddings import EmbeddingEngine
from task_engine.similarity import ContextSimilarityEngine
from task_engine.task_inference import TaskInferenceEngine
from task_engine.state_selector import StateSelector
from task_engine.handoff import HandoffBuilder


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


print()
print("TASK HANDOFF PACKAGES")
print("=====================")


for task in tasks:

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
    print(task.task_id)
    print(f"Label: {task.label}")
    print(
        f"Contexts in task: "
        f"{len(task_contexts)}"
    )
    print(
        f"Selected states: "
        f"{len(package.contexts)}"
    )

    total_cost = sum(
        state.cost
        for state in package.contexts
    )

    print(
        f"Total state cost: "
        f"{total_cost:.2f}"
    )

    for state in package.contexts:

        print(
            f"  {state.context_id}"
        )

        print(
            f"    representation: "
            f"{state.representation_id}"
        )

        print(
            f"    method: "
            f"{state.reconstruction_method}"
        )

        print(
            f"    cost: "
            f"{state.cost:.2f}"
        )

        print(
            f"    sufficiency: "
            f"{state.sufficiency_score:.3f}"
        )