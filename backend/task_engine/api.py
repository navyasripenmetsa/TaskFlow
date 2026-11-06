
from functools import lru_cache
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .activity_inference import ActivityInferenceEngine
from .embeddings import EmbeddingEngine
from .features import FeatureExtractor
from .handoff import HandoffBuilder
from .minimum_context_selector import MinimumContextSelector
from .normalizer import load_contexts
from .similarity import ContextSimilarityEngine
from .state_selector import StateSelector
from .task_inference import TaskInferenceEngine


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Task Processing"])


# --------------------------------------------------
# Request model
# --------------------------------------------------

class ContextProcessingRequest(BaseModel):
    schema_version: str = "1.0"
    captured_at: str | None = None
    context_count: int | None = None
    contexts: list[dict[str, Any]] = Field(...)


# --------------------------------------------------
# Initialize shared task-engine components
# --------------------------------------------------

@lru_cache(maxsize=1)
def get_task_engine_components():
    """
    Initialize the task-engine components once.

    The embedding model and feature extractor are shared
    wherever the existing constructors allow it.
    """

    logger.info("Initializing TaskFlow task engine...")

    embedding_engine = EmbeddingEngine()

    feature_extractor = FeatureExtractor()

    similarity_engine = ContextSimilarityEngine(
        embedding_engine=embedding_engine,
        feature_extractor=feature_extractor,
    )

    task_engine = TaskInferenceEngine(
        embedding_engine=embedding_engine,
        similarity_engine=similarity_engine,
    )

    activity_engine = ActivityInferenceEngine(
        embedding_engine=embedding_engine,
    )

    state_selector = StateSelector()

    minimum_context_selector = MinimumContextSelector(
        feature_extractor=feature_extractor,
        similarity_engine=similarity_engine,
    )

    handoff_builder = HandoffBuilder()

    logger.info("TaskFlow task engine initialized.")

    return {
        "task_engine": task_engine,
        "activity_engine": activity_engine,
        "state_selector": state_selector,
        "minimum_context_selector": minimum_context_selector,
        "handoff_builder": handoff_builder,
    }


# --------------------------------------------------
# Process captured contexts
# --------------------------------------------------

@router.post("/process-contexts")
def process_contexts(request: ContextProcessingRequest):

    if not request.contexts:
        raise HTTPException(
            status_code=400,
            detail="No contexts were provided.",
        )

    try:
        # 1. Normalize Chrome extension data.
        session_data = {
            "contexts": request.contexts,
        }

        contexts = load_contexts(session_data)

        if not contexts:
            raise HTTPException(
                status_code=400,
                detail="No valid contexts were found.",
            )

        # 2. Initialize or reuse shared components.
        components = get_task_engine_components()

        task_engine = components["task_engine"]
        activity_engine = components["activity_engine"]
        state_selector = components["state_selector"]
        minimum_context_selector = (
            components["minimum_context_selector"]
        )
        handoff_builder = components["handoff_builder"]

        # 3. Discover individual tasks.
        tasks = task_engine.discover_tasks(contexts)

        # 4. Group related tasks into activities.
        activities = activity_engine.discover_activities(
            tasks,
            contexts,
        )

        context_lookup = {
            context.context_id: context
            for context in contexts
        }

        processed_activities = []

        # 5. Optimize each activity independently.
        for activity in activities:

            activity_contexts = [
                context_lookup[context_id]
                for context_id in activity.context_ids
                if context_id in context_lookup
            ]

            if not activity_contexts:
                continue

            # Select sufficient representations.
            state_report = (
                state_selector.select_for_task_with_report(
                    activity_contexts
                )
            )

            selected_states = state_report["selected_states"]

            # Remove redundant contexts while preserving coverage.
            selection_report = minimum_context_selector.select(
                activity_contexts,
                selected_states,
            )

            optimized_states = selection_report["selected_states"]

            # Build the final activity package.
            handoff_package = handoff_builder.build_activity(
                activity,
                optimized_states,
            ).to_dict()

            processed_activities.append({
                "activity_id": activity.activity_id,
                "label": activity.label,
                "description": activity.description,
                "task_ids": activity.task_ids,
                "coherence": activity.coherence,

                "ready_for_handoff": bool(
                    handoff_package["contexts"]
                ),

                "handoff_package": handoff_package,

                "optimization": {
                    "context_count": len(activity_contexts),
                    "selected_state_count": len(selected_states),
                    "selected_context_count": (
                        selection_report["selected_context_count"]
                    ),
                    "removed_context_ids": (
                        selection_report["removed_context_ids"]
                    ),
                    "failed_context_ids": (
                        state_report["failed_context_ids"]
                    ),
                    "coverage": selection_report["coverage"],
                    "baseline_cost": selection_report["baseline_cost"],
                    "total_cost": selection_report["total_cost"],
                    "cost_reduction": (
                        selection_report["cost_reduction"]
                    ),
                },
            })

        return {
            "success": True,
            "context_count": len(contexts),
            "task_count": len(tasks),
            "activity_count": len(processed_activities),
            "activities": processed_activities,
        }

    except HTTPException:
        raise

    except Exception as error:
        logger.exception("TaskFlow context processing failed.")

        raise HTTPException(
            status_code=500,
            detail=f"Context processing failed: {str(error)}",
        ) from error
