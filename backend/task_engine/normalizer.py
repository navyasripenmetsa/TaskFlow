from typing import List
from .models import ContextItem
def load_contexts(session_data: dict) -> List[ContextItem]:
    contexts = []
    for item in session_data["contexts"]:
        context = ContextItem(
            context_id=item["context_id"],
            tab_id=item["source"]["tab_id"],
            window_id=item["source"]["window_id"],
            title=item["content"]["title"],
            url=item["content"]["url"],
            domain=item["content"]["domain"],
            text=item["content"].get("text", ""),
            active=item["state"]["active"],
            last_interaction=item["state"].get("last_interaction"),
            reconstruction_method=item["reconstruction"]["method"],
            reconstruction_target=item["reconstruction"]["target"],
            interaction_state=item["state"].copy(),
        )
        contexts.append(context)
    return contexts