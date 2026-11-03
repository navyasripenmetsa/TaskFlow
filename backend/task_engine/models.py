
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ContextItem:
    """
    Raw context extracted from one application resource.
    """

    context_id: str

    # Source identity
    tab_id: int
    window_id: int

    # Content
    title: str
    url: str
    domain: str
    text: str

    # Activity
    active: bool
    last_interaction: Optional[str]

    # Reconstruction information
    reconstruction_method: str
    reconstruction_target: str

    # Captured interaction state
    interaction_state: dict = field(default_factory=dict)


@dataclass
class TaskMembership:
    """
    Relationship between one context and one discovered task.
    """

    context_id: str
    task_id: str
    score: float

    evidence: Dict[str, float] = field(default_factory=dict)


@dataclass
class TaskCandidate:
    """
    A discovered user task.
    """

    task_id: str
    context_ids: List[str]

    label: str
    description: str

    coherence: float

    membership_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class StateRepresentation:
    """
    One possible representation of an application resource.
    """

    representation_id: str
    context_id: str

    method: str
    target: str

    state: Dict[str, Any] = field(default_factory=dict)

    preserved_capabilities: List[str] = field(default_factory=list)

    cost: float = 0.0


@dataclass
class SufficiencyResult:
    """
    Result of checking whether a state representation
    is sufficient to reconstruct a resource.
    """

    context_id: str
    representation_id: str

    sufficient: bool
    score: float

    missing_capabilities: List[str] = field(default_factory=list)

    reason: str = ""


@dataclass
class SelectedState:
    """
    Final state representation selected for one task resource.
    """

    context_id: str
    representation_id: str

    method: str
    target: str

    state: Dict[str, Any]

    cost: float
    sufficiency_score: float

@dataclass
class ActivityCandidate:
    """
    A broader activity containing related discovered tasks.
    """

    activity_id: str
    label: str
    description: str

    task_ids: List[str]
    context_ids: List[str]

    coherence: float = 0.0
