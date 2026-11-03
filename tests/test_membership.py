import json

from task_engine.embeddings import EmbeddingEngine
from task_engine.membership import TaskMembershipEngine
from task_engine.normalizer import load_contexts
from task_engine.similarity import ContextSimilarityEngine
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

membership_engine = TaskMembershipEngine(
    embedding_engine,
    similarity_engine,
)

memberships = (
    membership_engine.calculate_all_memberships(
        tasks,
        contexts,
    )
)


print()
print("TASK MEMBERSHIPS")
print("================")

for task in tasks:

    print()
    print(task.task_id)
    print(f"Label: {task.label}")

    task_memberships = [
        membership
        for membership in memberships
        if membership.task_id == task.task_id
    ]

    for membership in sorted(
        task_memberships,
        key=lambda item: item.score,
        reverse=True,
    ):

        print(
            f"  {membership.context_id}: "
            f"{membership.score:.3f}"
        )

        print(
            "    evidence: "
            f"semantic={membership.evidence['semantic']:.3f}, "
            f"lexical={membership.evidence['lexical']:.3f}, "
            f"relational={membership.evidence['relational']:.3f}, "
            f"temporal={membership.evidence['temporal']:.3f}, "
            f"activity={membership.evidence['activity']:.3f}"
        )