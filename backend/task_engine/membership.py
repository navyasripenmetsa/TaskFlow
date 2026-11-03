from typing import Dict, List

import numpy as np

from .features import FeatureExtractor
from .models import (
    ContextItem,
    TaskCandidate,
    TaskMembership,
)
from .embeddings import EmbeddingEngine
from .similarity import ContextSimilarityEngine


class TaskMembershipEngine:

    def __init__(
        self,
        embedding_engine: EmbeddingEngine,
        similarity_engine: ContextSimilarityEngine | None = None,
        feature_extractor: FeatureExtractor | None = None,
    ):
        self.embedding_engine = embedding_engine

        self.similarity_engine = (
            similarity_engine
            if similarity_engine is not None
            else ContextSimilarityEngine(
                embedding_engine
            )
        )

        self.feature_extractor = (
            feature_extractor
            if feature_extractor is not None
            else FeatureExtractor()
        )

    def calculate_memberships(
        self,
        task: TaskCandidate,
        contexts: List[ContextItem],
    ) -> List[TaskMembership]:

        task_contexts = [
            context
            for context in contexts
            if context.context_id in task.context_ids
        ]

        if len(task_contexts) == 1:
            context = task_contexts[0]
            return [
                TaskMembership(
                    context_id=context.context_id,
                    task_id=task.task_id,
                    score=1.0,
                    evidence={
                        "semantic": 1.0,
                        "lexical": 1.0,
                        "relational": 1.0,
                        "temporal": 1.0,
                        "activity": 1.0 if context.active else 0.0,
            },
        )
    ]

        similarity_matrix = (
            self.similarity_engine.build_similarity_matrix(
                contexts
            )
        )

        context_indices = {
            context.context_id: index
            for index, context in enumerate(contexts)
        }

        memberships = []

        for context in task_contexts:

            index = context_indices[
                context.context_id
            ]

            evidence = self._calculate_evidence(
                context,
                task_contexts,
                contexts,
                similarity_matrix,
                index,
            )

            score = self._combine_evidence(
                evidence
            )

            memberships.append(
                TaskMembership(
                    context_id=context.context_id,
                    task_id=task.task_id,
                    score=score,
                    evidence=evidence,
                )
            )

        return memberships

    def calculate_all_memberships(
        self,
        tasks: List[TaskCandidate],
        contexts: List[ContextItem],
    ) -> List[TaskMembership]:

        memberships = []

        for task in tasks:

            task_memberships = (
                self.calculate_memberships(
                    task,
                    contexts,
                )
            )

            memberships.extend(
                task_memberships
            )

        return memberships

    def _calculate_evidence(
        self,
        context: ContextItem,
        task_contexts: List[ContextItem],
        all_contexts: List[ContextItem],
        similarity_matrix: np.ndarray,
        context_index: int,
    ) -> Dict[str, float]:

        semantic = self._semantic_evidence(
            context,
            task_contexts,
        )

        lexical = self._lexical_evidence(
            context,
            task_contexts,
        )

        relational = self._relational_evidence(
            context,
            task_contexts,
            all_contexts,
            similarity_matrix,
            context_index,
        )

        temporal = self._temporal_evidence(
            context,
            task_contexts,
        )

        activity = (
            1.0
            if context.active
            else 0.0
        )

        return {
            "semantic": semantic,
            "lexical": lexical,
            "relational": relational,
            "temporal": temporal,
            "activity": activity,
        }

    def _semantic_evidence(
        self,
        context: ContextItem,
        task_contexts: List[ContextItem],
    ) -> float:

        if len(task_contexts) == 1:
            return 1.0

        embeddings = self.embedding_engine.encode_contexts(
            task_contexts
        )

        context_index = next(
            index
            for index, item in enumerate(task_contexts)
            if item.context_id == context.context_id
        )

        similarities = np.dot(
            embeddings,
            embeddings[context_index],
        )

        other_scores = [
            float(score)
            for index, score in enumerate(similarities)
            if index != context_index
        ]

        if not other_scores:
            return 1.0

        return float(
            np.mean(other_scores)
        )

    def _lexical_evidence(
        self,
        context: ContextItem,
        task_contexts: List[ContextItem],
    ) -> float:

        features = (
            self.feature_extractor.extract_many(
                task_contexts
            )
        )

        context_tokens = next(
            feature.tokens
            for feature in features
            if feature.context_id == context.context_id
        )

        if not context_tokens:
            return 0.0

        scores = []

        for feature in features:

            if feature.context_id == context.context_id:
                continue

            other_tokens = feature.tokens

            if not other_tokens:
                continue

            union = (
                context_tokens
                | other_tokens
            )

            intersection = (
                context_tokens
                & other_tokens
            )

            if not union:
                continue

            scores.append(
                len(intersection)
                / len(union)
            )

        if not scores:
            return 0.0

        return float(
            np.mean(scores)
        )

    def _relational_evidence(
        self,
        context: ContextItem,
        task_contexts: List[ContextItem],
        all_contexts: List[ContextItem],
        similarity_matrix: np.ndarray,
        context_index: int,
    ) -> float:

        if len(task_contexts) == 1:
            return 1.0

        task_indices = [
            index
            for index, item in enumerate(all_contexts)
            if item.context_id in {
                task_context.context_id
                for task_context in task_contexts
            }
        ]

        scores = []

        for index in task_indices:

            if index == context_index:
                continue

            scores.append(
                float(
                    similarity_matrix[
                        context_index,
                        index,
                    ]
                )
            )

        if not scores:
            return 1.0

        return float(
            np.mean(scores)
        )

    def _temporal_evidence(
        self,
        context: ContextItem,
        task_contexts: List[ContextItem],
    ) -> float:

        features = (
            self.feature_extractor.extract_many(
                task_contexts
            )
        )

        context_feature = next(
            feature
            for feature in features
            if feature.context_id == context.context_id
        )

        if context_feature.timestamp is None:
            return 0.0

        scores = []

        for feature in features:

            if feature.context_id == context.context_id:
                continue

            if feature.timestamp is None:
                continue

            difference = abs(
                (
                    context_feature.timestamp
                    - feature.timestamp
                ).total_seconds()
            )

            score = float(
                np.exp(
                    -difference / 3600.0
                )
            )

            scores.append(score)

        if not scores:
            return 0.0

        return float(
            np.mean(scores)
        )

    def _combine_evidence(
        self,
        evidence: Dict[str, float],
    ) -> float:

        weights = {
            "semantic": 0.35,
            "lexical": 0.20,
            "relational": 0.30,
            "temporal": 0.10,
            "activity": 0.05,
        }

        weighted_score = sum(
            weights[name]
            * evidence.get(name, 0.0)
            for name in weights
        )

        weight_sum = sum(
            weights.values()
        )

        return float(
            weighted_score / weight_sum
        )