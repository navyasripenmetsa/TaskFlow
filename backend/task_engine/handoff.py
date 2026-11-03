from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from .models import (
    SelectedState,
    TaskCandidate,
)


@dataclass
class HandoffState:
    """
    State required to reconstruct one resource
    on the destination device.
    """

    context_id: str
    representation_id: str
    reconstruction_method: str
    reconstruction_target: str

    state: Dict[str, Any]

    cost: float
    sufficiency_score: float


@dataclass
class HandoffPackage:
    """
    Complete task-level handoff package.
    """

    task_id: str
    task_label: str
    task_description: str
    contexts: List[HandoffState]

    def to_dict(self) -> dict:
        return asdict(self)


class HandoffBuilder:

    def build(
        self,
        task: TaskCandidate,
        selected_states: List[SelectedState],
    ) -> HandoffPackage:

        task_context_ids = set(
            task.context_ids
        )

        task_states = [
            selected_state
            for selected_state in selected_states
            if selected_state.context_id
            in task_context_ids
        ]

        handoff_states = []

        for selected_state in task_states:

            handoff_state = HandoffState(
                context_id=(
                    selected_state.context_id
                ),
                representation_id=(
                    selected_state.representation_id
                ),
                reconstruction_method=(
                    selected_state.method
                ),
                reconstruction_target=(
                    selected_state.target
                ),
                state=selected_state.state,
                cost=selected_state.cost,
                sufficiency_score=(
                    selected_state.sufficiency_score
                ),
            )

            handoff_states.append(
                handoff_state
            )

        return HandoffPackage(
            task_id=task.task_id,
            task_label=task.label,
            task_description=task.description,
            contexts=handoff_states,
        )