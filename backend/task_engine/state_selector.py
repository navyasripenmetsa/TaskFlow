from typing import List

from .models import (
    ContextItem,
    SelectedState,
)
from .state_representation import (
    StateRepresentationEngine,
)
from .sufficiency import (
    SufficiencyEngine,
)


class StateSelector:

    def __init__(
        self,
        representation_engine: StateRepresentationEngine | None = None,
        sufficiency_engine: SufficiencyEngine | None = None,
    ):
        self.representation_engine = (
            representation_engine
            if representation_engine is not None
            else StateRepresentationEngine()
        )

        self.sufficiency_engine = (
            sufficiency_engine
            if sufficiency_engine is not None
            else SufficiencyEngine()
        )

    def select_for_context(
        self,
        context: ContextItem,
    ) -> SelectedState | None:

        representations = (
            self.representation_engine.generate(
                context
            )
        )

        sufficiency_results = (
            self.sufficiency_engine.check_many(
                context,
                representations,
            )
        )

        sufficient_representations = []

        for representation, result in zip(
            representations,
            sufficiency_results,
        ):

            if result.sufficient:
                sufficient_representations.append(
                    (
                        representation,
                        result,
                    )
                )

        if not sufficient_representations:

            fallback_representation = next(
                (
                    representation
                    for representation in representations
                    if representation.method
                    == "original_context_fallback"
                ),
                None,
            )

            if fallback_representation is None:
                return None

            return SelectedState(
                context_id=context.context_id,
                representation_id=(
                    fallback_representation.representation_id
                ),
                method=fallback_representation.method,
                target=fallback_representation.target,
                state=fallback_representation.state,
                cost=fallback_representation.cost,
                sufficiency_score=1.0,
            )

        selected_representation, selected_result = min(
            sufficient_representations,
            key=lambda item: item[0].cost,
        )

        return SelectedState(
            context_id=context.context_id,
            representation_id=(
                selected_representation.representation_id
            ),
            method=selected_representation.method,
            target=selected_representation.target,
            state=selected_representation.state,
            cost=selected_representation.cost,
            sufficiency_score=selected_result.score,
        )

    def select_for_task(
        self,
        task_contexts: List[ContextItem],
    ) -> List[SelectedState]:

        selected_states = []

        for context in task_contexts:

            selected_state = (
                self.select_for_context(
                    context
                )
            )

            if selected_state is not None:
                selected_states.append(
                    selected_state
                )

        return selected_states

    def select_for_task_with_report(
        self,
        task_contexts: List[ContextItem],
    ) -> dict:

        selected_states = []
        failed_contexts = []

        for context in task_contexts:

            selected_state = (
                self.select_for_context(
                    context
                )
            )

            if selected_state is None:
                failed_contexts.append(
                    context.context_id
                )
            else:
                selected_states.append(
                    selected_state
                )

        total_cost = sum(
            state.cost
            for state in selected_states
        )

        return {
            "selected_states": selected_states,
            "failed_context_ids": failed_contexts,
            "total_cost": total_cost,
            "context_count": len(task_contexts),
            "selected_state_count": len(
                selected_states
            ),
        }