
from datetime import datetime
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .embeddings import EmbeddingEngine
from .features import FeatureExtractor
from .models import ContextItem


class ContextSimilarityEngine:
    """
    Calculates similarity between contexts using multiple
    independent signals:

    1. Semantic similarity
    2. Lexical similarity
    3. Temporal similarity
    4. Activity similarity
    """

    def __init__(
        self,
        embedding_engine: EmbeddingEngine,
        feature_extractor: FeatureExtractor | None = None,
        semantic_weight: float = 0.55,
        lexical_weight: float = 0.20,
        temporal_weight: float = 0.10,
        activity_weight: float = 0.05,
    ):
        self.embedding_engine = embedding_engine

        self.feature_extractor = (
            feature_extractor
            or FeatureExtractor()
        )

        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.temporal_weight = temporal_weight
        self.activity_weight = activity_weight

    # ---------------------------------------------------------
    # Semantic similarity
    # ---------------------------------------------------------

    def semantic_similarity(
        self,
        contexts: List[ContextItem],
    ) -> np.ndarray:

        embeddings = (
            self.embedding_engine.encode_contexts(contexts)
        )

        return cosine_similarity(embeddings)

    # ---------------------------------------------------------
    # Lexical similarity
    # ---------------------------------------------------------

    def lexical_similarity(
        self,
        contexts: List[ContextItem],
    ) -> np.ndarray:

        features = (
            self.feature_extractor.extract_many(contexts)
        )

        documents = [
            " ".join(sorted(feature.tokens))
            for feature in features
        ]

        if not any(documents):
            return np.zeros(
                (len(contexts), len(contexts))
            )

        vectorizer = TfidfVectorizer(
            lowercase=False,
            token_pattern=r"(?u)\b\w+\b",
        )

        matrix = vectorizer.fit_transform(documents)

        return cosine_similarity(matrix)

    # ---------------------------------------------------------
    # Temporal similarity
    # ---------------------------------------------------------

    def _parse_timestamp(
        self,
        context: ContextItem,
    ) -> datetime | None:

        if not context.last_interaction:
            return None

        try:
            return datetime.fromisoformat(
                context.last_interaction.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return None

    def _temporal_similarity(
        self,
        context_a: ContextItem,
        context_b: ContextItem,
    ) -> float | None:

        timestamp_a = self._parse_timestamp(context_a)
        timestamp_b = self._parse_timestamp(context_b)

        # Missing timestamps are unavailable evidence,
        # not evidence that two contexts are unrelated.
        if timestamp_a is None or timestamp_b is None:
            return None

        # Avoid subtracting timezone-aware and naive timestamps.
        if (
            timestamp_a.tzinfo is None
        ) != (
            timestamp_b.tzinfo is None
        ):
            return None

        difference = abs(
            (
                timestamp_a - timestamp_b
            ).total_seconds()
        )

        # One-hour half-life.
        half_life = 3600.0

        return float(
            np.exp(
                -np.log(2)
                * difference
                / half_life
            )
        )

    # ---------------------------------------------------------
    # Activity similarity
    # ---------------------------------------------------------

    def _activity_similarity(
        self,
        context_a: ContextItem,
        context_b: ContextItem,
    ) -> float:

        if context_a.active and context_b.active:
            return 1.0

        if not context_a.active and not context_b.active:
            return 0.5

        return 0.0

    # ---------------------------------------------------------
    # Combined similarity
    # ---------------------------------------------------------

    def build_similarity_matrix(
        self,
        contexts: List[ContextItem],
    ) -> np.ndarray:

        if not contexts:
            return np.empty((0, 0))

        semantic = self.semantic_similarity(contexts)
        lexical = self.lexical_similarity(contexts)

        n = len(contexts)

        similarity = np.zeros((n, n))

        for i in range(n):
            for j in range(n):

                temporal = self._temporal_similarity(
                    contexts[i],
                    contexts[j],
                )

                activity = self._activity_similarity(
                    contexts[i],
                    contexts[j],
                )

                signals = [
                    (self.semantic_weight, semantic[i, j]),
                    (self.lexical_weight, lexical[i, j]),
                    (self.temporal_weight, temporal),
                    (self.activity_weight, activity),
                ]

                # Exclude unavailable signals from both
                # the weighted score and its denominator.
                available_signals = [
                    (weight, value)
                    for weight, value in signals
                    if weight > 0 and value is not None
                ]

                weight_sum = sum(
                    weight
                    for weight, _ in available_signals
                )

                if weight_sum > 0:
                    score = sum(
                        weight * value
                        for weight, value in available_signals
                    ) / weight_sum
                else:
                    score = 0.0

                similarity[i, j] = score

        # A context is perfectly similar to itself.
        np.fill_diagonal(similarity, 1.0)

        return similarity
