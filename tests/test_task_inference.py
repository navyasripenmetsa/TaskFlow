import json

from task_engine.normalizer import load_contexts
from task_engine.embeddings import EmbeddingEngine
from task_engine.similarity import ContextSimilarityEngine
from task_engine.task_inference import TaskInferenceEngine


with open(
    "data/test_session.json",
    "r",
    encoding="utf-8",
) as f:

    session_data = json.load(f)


contexts = load_contexts(
    session_data
)

embedding_engine = EmbeddingEngine()

similarity_engine = ContextSimilarityEngine(
    embedding_engine
)

task_engine = TaskInferenceEngine(
    embedding_engine=embedding_engine,
    similarity_engine=similarity_engine,
    merge_threshold=0.35,
    coherence_threshold=0.30,
)

tasks = task_engine.discover_tasks(
    contexts
)


print()
print("DISCOVERED TASKS")
print("================")

for task in tasks:

    print()
    print(task.task_id)

    print(
        "Label:",
        task.label,
    )

    print(
        "Coherence:",
        round(task.coherence, 3),
    )

    print(
        "Description:",
        task.description,
    )

    print("Contexts:")

    for context_id in task.context_ids:

        print(
            "  -",
            context_id,
        )