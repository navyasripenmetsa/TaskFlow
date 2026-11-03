import json

from task_engine.normalizer import load_contexts
from task_engine.state_representation import (
    StateRepresentationEngine,
)
from task_engine.sufficiency import (
    SufficiencyEngine,
)


with open(
    "data/test_session.json",
    "r",
    encoding="utf-8",
) as file:
    session_data = json.load(file)


contexts = load_contexts(session_data)

representation_engine = (
    StateRepresentationEngine()
)

sufficiency_engine = (
    SufficiencyEngine()
)


print()
print("STATE SUFFICIENCY")
print("=================")


for context in contexts[:2]:

    representations = (
        representation_engine.generate(
            context
        )
    )

    print()
    print(context.context_id)
    print(f"Title: {context.title}")

    results = (
        sufficiency_engine.check_many(
            context,
            representations,
        )
    )

    for result in results:

        print(
            f"  {result.representation_id}"
        )

        print(
            f"    sufficient: "
            f"{result.sufficient}"
        )

        print(
            f"    score: "
            f"{result.score:.3f}"
        )

        print(
            f"    missing: "
            f"{result.missing_capabilities}"
        )

        print(
            f"    reason: "
            f"{result.reason}"
        )