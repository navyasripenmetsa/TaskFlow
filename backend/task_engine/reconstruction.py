from typing import Any, Dict
from .handoff import HandoffState


class ReconstructionEngine:

    def reconstruct(
        self,
        handoff_state: HandoffState,
    ) -> Dict[str, Any]:

        method = (
            handoff_state.reconstruction_method
        )

        if method == "url":
            return self._reconstruct_url(
                handoff_state
            )

        if method == "url_with_metadata":
            return self._reconstruct_url_with_metadata(
                handoff_state
            )

        if method == "url_with_content":
            return self._reconstruct_url_with_content(
                handoff_state
            )

        return {
            "success": False,
            "context_id": (
                handoff_state.context_id
            ),
            "method": method,
            "action": "unsupported",
            "target": (
                handoff_state.reconstruction_target
            ),
            "message": (
                "Reconstruction method is "
                "not supported yet."
            ),
        }

    def _reconstruct_url(
        self,
        handoff_state: HandoffState,
    ) -> Dict[str, Any]:

        return {
            "success": True,
            "context_id": (
                handoff_state.context_id
            ),
            "method": "url",
            "action": "open_url",
            "target": (
                handoff_state.reconstruction_target
            ),
            "message": (
                "Open "
                + handoff_state.reconstruction_target
            ),
        }

    def _reconstruct_url_with_metadata(
        self,
        handoff_state: HandoffState,
    ) -> Dict[str, Any]:

        return {
            "success": True,
            "context_id": (
                handoff_state.context_id
            ),
            "method": "url_with_metadata",
            "action": "open_url",
            "target": (
                handoff_state.reconstruction_target
            ),
            "state": handoff_state.state,
            "message": (
                "Open the resource using the "
                "reconstruction target and "
                "preserve the supplied metadata."
            ),
        }

    def _reconstruct_url_with_content(
        self,
        handoff_state: HandoffState,
    ) -> Dict[str, Any]:

        return {
            "success": True,
            "context_id": (
                handoff_state.context_id
            ),
            "method": "url_with_content",
            "action": "open_url",
            "target": (
                handoff_state.reconstruction_target
            ),
            "state": handoff_state.state,
            "message": (
                "Open the resource using the "
                "reconstruction target and "
                "preserve the supplied content "
                "context."
            ),
        }