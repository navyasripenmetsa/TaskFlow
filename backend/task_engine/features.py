
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Set

from nltk.corpus import stopwords

from .models import ContextItem


@dataclass
class ContextFeatures:
    """
    General features extracted from one context.
    """

    context_id: str
    semantic_text: str
    tokens: Set[str]
    entities: Set[str]
    timestamp: datetime | None
    active: bool


class FeatureExtractor:
    """
    Extracts domain-independent features from ContextItem objects.

    Stopwords come from a standard NLP resource rather than
    a manually maintained project-specific list.
    """

    def __init__(self):
        self.stopwords = set(stopwords.words("english"))

    def extract(
        self,
        context: ContextItem,
    ) -> ContextFeatures:

        return ContextFeatures(
            context_id=context.context_id,
            semantic_text=self._build_semantic_text(context),
            tokens=self._extract_tokens(context),
            entities=self._extract_entities(context),
            timestamp=self._parse_timestamp(
                context.last_interaction
            ),
            active=context.active,
        )

    def extract_many(
        self,
        contexts: List[ContextItem],
    ) -> List[ContextFeatures]:

        return [
            self.extract(context)
            for context in contexts
        ]

    def _build_semantic_text(
        self,
        context: ContextItem,
    ) -> str:

        parts = [
            context.title.strip(),
            context.domain.strip(),
            context.text.strip(),
        ]

        return " ".join(
            part
            for part in parts
            if part
        )

    def _extract_tokens(
        self,
        context: ContextItem,
    ) -> Set[str]:

        text = self._build_semantic_text(context).lower()

        tokens: Set[str] = set()
        current_token: List[str] = []

        for character in text:

            if character.isalnum():
                current_token.append(character)
                continue

            self._add_token(
                current_token,
                tokens,
            )

            current_token = []

        self._add_token(
            current_token,
            tokens,
        )

        return tokens

    def _add_token(
        self,
        current_token: List[str],
        tokens: Set[str],
    ):

        if len(current_token) < 3:
            return

        token = "".join(current_token)

        if token in self.stopwords:
            return

        tokens.add(token)

    def _extract_entities(
        self,
        context: ContextItem,
    ) -> Set[str]:

        text = " ".join([
            context.title,
            context.domain,
            context.text,
        ])

        # Common task-related words that are not named entities.
        generic_words = {
            "trip", "planning", "booking", "confirmation",
            "travel", "search", "results", "weather",
            "forecast", "guide", "vlog", "hotels",
            "flight", "flights", "reservation",
            "check", "find", "organize", "organizing",
            "user", "google", "gmail",
        }

        entities: Set[str] = set()

        # Extract individual capitalized words and acronyms.
        pattern = r"\b[A-Z][a-z]{2,}\b|\b[A-Z]{2,}\b"

        for match in re.findall(pattern, text):
            entity = match.strip().lower()

            if (
                entity not in self.stopwords
                and entity not in generic_words
            ):
                entities.add(entity)

        return entities


    def _parse_timestamp(
        self,
        timestamp: str | None,
    ) -> datetime | None:

        if not timestamp:
            return None

        try:
            return datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        except ValueError:
            return None
