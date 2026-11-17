"""Run the TaskFlow activity handoff generator against a captured session.

The default output is a separate generated file so this utility never replaces
the bundled Android sample handoff.
"""

import argparse
import json
from pathlib import Path

from backend.handoff_pipeline import generate_activity_handoff


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/real_session.json"),
        help="Chrome extension capture JSON (default: data/real_session.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/generated_activity_handoff.json"),
        help="Android-format handoff JSON output path",
    )
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as source:
        capture = json.load(source)

    document = generate_activity_handoff(capture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as destination:
        json.dump(document, destination, indent=2, ensure_ascii=False)

    print(f"Generated {len(document['activities'])} activity handoff(s).")
    print(f"Handoff export saved to {args.output}")


if __name__ == "__main__":
    main()
