import json

from task_engine.normalizer import load_contexts
from task_engine.state_selector import StateSelector


with open(
    "data/test_session.json",
    "r",
    encoding="utf-8",
) as file:
    session_data = json.load(file)


contexts = load_contexts(session_data)

selector = StateSelector()


print()
print("MINIMUM SUFFICIENT STATE SELECTION")
print("===================================")


for context in contexts[:3]:

    result = selector.select_for_context(
        context
    )

    print()
    print(context.context_id)
    print(f"Title: {context.title}")

    if result is None:

        print(
            "  No sufficient representation found."
        )

        continue

    print(
        f"  Selected representation: "
        f"{result.representation_id}"
    )

    print(
        f"  Method: {result.method}"
    )

    print(
        f"  Cost: {result.cost:.2f}"
    )

    print(
        f"  Sufficiency score: "
        f"{result.sufficiency_score:.3f}"
    )

    print(
        f"  Target: {result.target}"
    )