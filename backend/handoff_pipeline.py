"""Reusable laptop-to-phone handoff generation pipeline."""

from functools import lru_cache
import math
from threading import RLock
from urllib.parse import urlsplit

from .task_engine.activity_inference import ActivityInferenceEngine
from .task_engine.embeddings import EmbeddingEngine
from .task_engine.handoff import HandoffBuilder
from .task_engine.normalizer import load_contexts
from .task_engine.state_selector import StateSelector
from .task_engine.task_inference import TaskInferenceEngine


class HandoffGenerationError(ValueError):
    """Raised when captured contexts cannot produce an Android handoff."""


_PIPELINE_LOCK = RLock()


@lru_cache(maxsize=1)
def _shared_embedding_engine() -> EmbeddingEngine:
    # Load the transformer once per server process, on the first capture.
    return EmbeddingEngine()


def generate_activity_handoff(
    capture: dict,
    *,
    embedding_engine: EmbeddingEngine | None = None,
) -> dict:
    """Turn a Chrome extension capture into the Android parser's document shape.

    This function has no file or network side effects. The caller owns delivery
    and persistence of the returned ``{"activities": [...]}`` document.
    """
    if not isinstance(capture, dict):
        raise HandoffGenerationError("Capture must be a JSON object.")

    raw_contexts = capture.get("contexts")
    if not isinstance(raw_contexts, list) or not raw_contexts:
        raise HandoffGenerationError("Capture contains no browser contexts.")
    validate_extension_capture(capture)

    try:
        contexts = load_contexts(capture)
    except (KeyError, TypeError, ValueError) as error:
        raise HandoffGenerationError(
            f"Captured context fields are incomplete: {error}"
        ) from error

    engine = embedding_engine or _shared_embedding_engine()

    # The model and clustering engines are reused by one server process. Keep
    # inference serial so two simultaneous sends do not compete for the model.
    with _PIPELINE_LOCK:
        task_engine = TaskInferenceEngine(embedding_engine=engine)
        tasks = task_engine.discover_tasks(contexts)
        if not tasks:
            raise HandoffGenerationError(
                "Task inference did not find a task in the captured tabs."
            )

        activity_engine = ActivityInferenceEngine(embedding_engine=engine)
        activities = activity_engine.discover_activities(tasks, contexts=contexts)
        if not activities:
            raise HandoffGenerationError(
                "Activity inference did not find an activity in the captured tabs."
            )

        state_selector = StateSelector()
        handoff_builder = HandoffBuilder()
        context_by_id = {context.context_id: context for context in contexts}
        task_by_id = {task.task_id: task for task in tasks}
        document = {"activities": []}

        for activity in activities:
            activity_export = {
                "activity_id": activity.activity_id,
                "activity_label": activity.label,
                "handoff_packages": [],
                "activity_handoff_package": None,
            }
            activity_selected_states = []

            for task_id in activity.task_ids:
                task = task_by_id.get(task_id)
                if task is None:
                    raise HandoffGenerationError(
                        f"Activity references an unknown task '{task_id}'."
                    )

                task_contexts = [
                    context_by_id[context_id]
                    for context_id in task.context_ids
                    if context_id in context_by_id
                ]
                report = state_selector.select_for_task_with_report(
                    task_contexts
                )
                selected_states = report["selected_states"]
                if not selected_states:
                    raise HandoffGenerationError(
                        f"No reconstructable contexts were selected for task '{task.label}'."
                    )

                activity_selected_states.extend(selected_states)
                task_package = handoff_builder.build(task, selected_states)
                _complete_context_state(task_package.contexts, context_by_id)
                activity_export["handoff_packages"].append(
                    task_package.to_dict()
                )

            activity_package = handoff_builder.build_activity(
                activity,
                activity_selected_states,
            )
            _complete_context_state(activity_package.contexts, context_by_id)
            activity_export["activity_handoff_package"] = (
                activity_package.to_dict()
            )
            document["activities"].append(activity_export)

    validate_android_handoff_document(document)
    return document


def _complete_context_state(handoff_contexts, context_by_id: dict) -> None:
    """Ensure every generated context has the fields Android renders."""
    for handoff_context in handoff_contexts:
        source = context_by_id.get(handoff_context.context_id)
        if source is None:
            raise HandoffGenerationError(
                f"Generated context '{handoff_context.context_id}' has no source tab."
            )

        target = handoff_context.reconstruction_target or source.url
        state = dict(handoff_context.state or {})
        state["url"] = _nonblank(state.get("url")) or target
        state["title"] = (
            _nonblank(state.get("title"))
            or _nonblank(source.title)
            or "Untitled tab"
        )
        state["domain"] = (
            _nonblank(state.get("domain"))
            or _nonblank(source.domain)
            or urlsplit(target).hostname
            or "unknown"
        )
        handoff_context.reconstruction_target = target
        handoff_context.state = state


def _nonblank(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def validate_extension_capture(capture: dict) -> None:
    """Validate the extension's captured-context schema before inference."""
    contexts = capture.get("contexts")
    if len(contexts) > 100:
        raise HandoffGenerationError("Capture may contain at most 100 tabs.")

    seen_ids = set()
    for index, context in enumerate(contexts):
        path = f"contexts[{index}]"
        if not isinstance(context, dict):
            raise HandoffGenerationError(f"{path} must be an object.")

        context_id = _required_text(context, "context_id", path)
        if context_id in seen_ids:
            raise HandoffGenerationError(f"Duplicate context_id '{context_id}'.")
        seen_ids.add(context_id)

        source = context.get("source")
        if not isinstance(source, dict):
            raise HandoffGenerationError(f"{path}.source must be an object.")
        for field in ("tab_id", "window_id"):
            number = source.get(field)
            if isinstance(number, bool) or not isinstance(number, int):
                raise HandoffGenerationError(
                    f"{path}.source.{field} must be an integer."
                )

        content = context.get("content")
        if not isinstance(content, dict):
            raise HandoffGenerationError(f"{path}.content must be an object.")
        for field in ("title", "url", "domain", "text"):
            value = content.get(field)
            if not isinstance(value, str):
                raise HandoffGenerationError(
                    f"{path}.content.{field} must be a string."
                )
        parsed_url = urlsplit(content["url"])
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise HandoffGenerationError(
                f"{path}.content.url must be an HTTP(S) URL."
            )

        state = context.get("state")
        if not isinstance(state, dict) or not isinstance(state.get("active"), bool):
            raise HandoffGenerationError(
                f"{path}.state.active must be a boolean."
            )

        reconstruction = context.get("reconstruction")
        if not isinstance(reconstruction, dict):
            raise HandoffGenerationError(
                f"{path}.reconstruction must be an object."
            )
        method = _required_text(reconstruction, "method", f"{path}.reconstruction")
        target = _required_text(reconstruction, "target", f"{path}.reconstruction")
        if method not in {"url", "url_with_metadata", "url_with_content"}:
            raise HandoffGenerationError(
                f"{path}.reconstruction.method is not supported."
            )
        parsed_target = urlsplit(target)
        if parsed_target.scheme not in {"http", "https"} or not parsed_target.hostname:
            raise HandoffGenerationError(
                f"{path}.reconstruction.target must be an HTTP(S) URL."
            )

    total_text_chars = sum(len(context["content"]["text"]) for context in contexts)
    if total_text_chars > 1_500_000:
        raise HandoffGenerationError(
            "Captured page text exceeds the 1.5 million character limit."
        )


def validate_android_handoff_document(document: dict) -> None:
    """Validate the document before it reaches the device inbox."""
    if not isinstance(document, dict):
        raise HandoffGenerationError("Generated handoff must be an object.")

    activities = document.get("activities")
    if not isinstance(activities, list) or not activities:
        raise HandoffGenerationError(
            "Generated handoff contains no activities."
        )

    for activity_index, activity in enumerate(activities):
        path = f"activities[{activity_index}]"
        if not isinstance(activity, dict):
            raise HandoffGenerationError(f"{path} must be an object.")
        _required_text(activity, "activity_id", path)
        _required_text(activity, "activity_label", path)

        task_packages = activity.get("handoff_packages")
        if not isinstance(task_packages, list):
            raise HandoffGenerationError(f"{path}.handoff_packages must be an array.")
        for task_index, task in enumerate(task_packages):
            task_path = f"{path}.handoff_packages[{task_index}]"
            if not isinstance(task, dict):
                raise HandoffGenerationError(f"{task_path} must be an object.")
            for field in ("task_id", "task_label", "task_description"):
                _required_text(task, field, task_path)
            contexts = task.get("contexts")
            if not isinstance(contexts, list):
                raise HandoffGenerationError(f"{task_path}.contexts must be an array.")
            for context_index, context in enumerate(contexts):
                _validate_context(
                    context,
                    f"{task_path}.contexts[{context_index}]",
                )

        activity_package = activity.get("activity_handoff_package")
        if activity_package is not None:
            if not isinstance(activity_package, dict):
                raise HandoffGenerationError(
                    f"{path}.activity_handoff_package must be an object or null."
                )
            package_path = f"{path}.activity_handoff_package"
            for field in ("activity_id", "activity_label", "activity_description"):
                _required_text(activity_package, field, package_path)
            task_ids = activity_package.get("task_ids")
            if not isinstance(task_ids, list) or any(
                not _nonblank(task_id) for task_id in task_ids
            ):
                raise HandoffGenerationError(
                    f"{package_path}.task_ids must be an array of non-empty strings."
                )
            contexts = activity_package.get("contexts")
            if not isinstance(contexts, list):
                raise HandoffGenerationError(
                    f"{package_path}.contexts must be an array."
                )
            for context_index, context in enumerate(contexts):
                _validate_context(
                    context,
                    f"{package_path}.contexts[{context_index}]",
                )


def _required_text(value: dict, field: str, path: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise HandoffGenerationError(
            f"{path}.{field} must be a non-empty string."
        )
    return result


def _validate_context(context, path: str) -> None:
    if not isinstance(context, dict):
        raise HandoffGenerationError(f"{path} must be an object.")
    for field in (
        "context_id",
        "representation_id",
        "reconstruction_method",
        "reconstruction_target",
    ):
        _required_text(context, field, path)

    target = context["reconstruction_target"]
    parsed_target = urlsplit(target)
    if parsed_target.scheme not in {"http", "https"} or not parsed_target.hostname:
        raise HandoffGenerationError(
            f"{path}.reconstruction_target must be an HTTP(S) URL."
        )

    state = context.get("state")
    if not isinstance(state, dict):
        raise HandoffGenerationError(f"{path}.state must be an object.")
    for field in ("url", "title", "domain"):
        _required_text(state, field, f"{path}.state")

    for field in ("cost", "sufficiency_score"):
        number = context.get(field)
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(number)
        ):
            raise HandoffGenerationError(
                f"{path}.{field} must be a finite number."
            )
