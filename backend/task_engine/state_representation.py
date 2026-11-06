from typing import List

from .models import ContextItem, StateRepresentation


class StateRepresentationEngine:

    def generate(
        self,
        context: ContextItem,
    ) -> List[StateRepresentation]:

        representations = []

        # Representation 1:
        # Reconstruct the resource using its target URL.
        representations.append(
            StateRepresentation(
                representation_id=(
                    f"{context.context_id}_url"
                ),
                context_id=context.context_id,
                method="url",
                target=context.reconstruction_target,
                state={
                    "url": context.reconstruction_target,
                    "title": context.title,
                },
                preserved_capabilities=[
                    "resource_identity",
                    "resource_access",
                ],
                cost=1.0,
            )
        )

        # Representation 2:
        # Preserve additional page metadata.
        representations.append(
            StateRepresentation(
                representation_id=(
                    f"{context.context_id}_metadata"
                ),
                context_id=context.context_id,
                method="url_with_metadata",
                target=context.reconstruction_target,
                state={
                    "url": context.reconstruction_target,
                    "title": context.title,
                    "domain": context.domain,
                },
                preserved_capabilities=[
                    "resource_identity",
                    "resource_access",
                    "page_identity",
                ],
                cost=1.5,
            )
        )

        # Representation 3:
        # Preserve the extracted semantic page content
        # together with the reconstruction target.
        if context.text.strip():

            representations.append(
                StateRepresentation(
                    representation_id=(
                        f"{context.context_id}_content"
                    ),
                    context_id=context.context_id,
                    method="url_with_content",
                    target=context.reconstruction_target,
                    state={
                        "url": context.reconstruction_target,
                        "title": context.title,
                        "domain": context.domain,
                        "text": context.text,
                    },
                    preserved_capabilities=[
                        "resource_identity",
                        "resource_access",
                        "page_identity",
                        "semantic_context",
                    ],
                    cost=2.0,
                )
            )

            
        # Representation 4:
        # Preserve spreadsheet data when this context contains it.
        spreadsheet_data = context.interaction_state.get(
            "spreadsheet_data"
        )
        if spreadsheet_data:
            representations.append(
                StateRepresentation(
                    representation_id=(
                        f"{context.context_id}_spreadsheet"
                    ),
                    context_id=context.context_id,
                    method="url_with_spreadsheet_data",
                    target=context.reconstruction_target,
                    state={
                        "url": context.reconstruction_target,
                        "title": context.title,
                        "spreadsheet_data": spreadsheet_data,
                    },
                    preserved_capabilities=[
                        "resource_identity",
                        "resource_access",
                        "page_identity",
                        "spreadsheet_data",
                    ],
                    cost=3.0,
                )
            )
        # Representation 5:
        # Preserve the complete original context as a fallback.
        # This ensures that a captured tab is never lost when
        # compact representations are insufficient.
        representations.append(
            StateRepresentation(
                representation_id=(
                    f"{context.context_id}_original_fallback"
                ),
                context_id=context.context_id,
                method="original_context_fallback",
                target=context.reconstruction_target,
                state={
                    "context_id": context.context_id,
                    "tab_id": context.tab_id,
                    "window_id": context.window_id,
                    "title": context.title,
                    "url": context.url,
                    "domain": context.domain,
                    "text": context.text,
                    "active": context.active,
                    "last_interaction": context.last_interaction,
                    "reconstruction_method": (
                        context.reconstruction_method
                    ),
                    "reconstruction_target": (
                        context.reconstruction_target
                    ),
                    "interaction_state": (
                        context.interaction_state.copy()
                    ),
                },
                preserved_capabilities=[
                    "resource_identity",
                    "resource_access",
                    "page_identity",
                    "semantic_context",
                    "spreadsheet_data",
                    "complete_context",
                ],
                cost=10.0,
            )
        )
        return representations

    def generate_many(
        self,
        contexts: List[ContextItem],
    ) -> List[StateRepresentation]:

        representations = []

        for context in contexts:
            representations.extend(
                self.generate(context)
            )

        return representations