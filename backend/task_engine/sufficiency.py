from typing import List

from .models import (
    ContextItem,
    StateRepresentation,
    SufficiencyResult,
)


class SufficiencyEngine:

    def check(
        self,
        context: ContextItem,
        representation: StateRepresentation,
    ) -> SufficiencyResult:

        preserved = set(
            representation.preserved_capabilities
        )

        required = self._required_capabilities(
            context
        )

        missing = sorted(
            required - preserved
        )

        sufficient = len(missing) == 0

        score = self._calculate_score(
            required,
            preserved,
        )

        reason = self._build_reason(
            sufficient,
            missing,
        )

        return SufficiencyResult(
            context_id=context.context_id,
            representation_id=(
                representation.representation_id
            ),
            sufficient=sufficient,
            score=score,
            missing_capabilities=missing,
            reason=reason,
        )

    def check_many(
        self,
        context: ContextItem,
        representations: List[StateRepresentation],
    ) -> List[SufficiencyResult]:

        return [
            self.check(
                context,
                representation,
            )
            for representation in representations
        ]

    def _required_capabilities(
        self,
        context: ContextItem,
    ) -> set[str]:

        required = {
            "resource_identity",
            "resource_access",
        }

        if context.title.strip():
            required.add("page_identity")

        # Spreadsheet data must be preserved when available.
        if context.interaction_state.get("spreadsheet_data"):
            required.add("spreadsheet_data")

        return required

    def _calculate_score(
        self,
        required: set[str],
        preserved: set[str],
    ) -> float:

        if not required:
            return 1.0

        covered = (
            required & preserved
        )

        return len(covered) / len(required)

    def _build_reason(
        self,
        sufficient: bool,
        missing: List[str],
    ) -> str:

        if sufficient:
            return (
                "Representation preserves "
                "all required capabilities."
            )

        return (
            "Representation is missing: "
            + ", ".join(missing)
        )