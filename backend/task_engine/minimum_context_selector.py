from typing import List, Dict, Any
from math import log

from .models import ContextItem, SelectedState
from .features import FeatureExtractor
from .similarity import ContextSimilarityEngine


class MinimumContextSelector:

    def __init__(
        self,
        coverage_threshold: float = 0.90,
        feature_extractor: FeatureExtractor | None = None,
        similarity_engine: ContextSimilarityEngine | None = None,
    ):

        if not 0.0 < coverage_threshold <= 1.0:
            raise ValueError(
                "coverage_threshold must be between 0 and 1"
            )

        self.coverage_threshold = coverage_threshold

        self.feature_extractor = (
            feature_extractor
            if feature_extractor is not None
            else FeatureExtractor()
        )

        self.similarity_engine = similarity_engine

    def extract_task_information(
        self,
        task_contexts: List[ContextItem],
    ) -> Dict[str, Any]:

        features = self.feature_extractor.extract_many(
            task_contexts
        )

        information = {}

        for feature in features:

            information[feature.context_id] = {
                "tokens": feature.tokens,
                "timestamp": feature.timestamp,
                "active": feature.active,
            }

        return information

    def _calculate_information_weights(
        self,
        information: Dict[str, Any],
    ) -> Dict[str, float]:

        document_frequency = {}

        for item in information.values():

            for token in item["tokens"]:

                document_frequency[token] = (
                    document_frequency.get(token, 0) + 1
                )

        context_count = len(information)

        weights = {}

        for token, frequency in document_frequency.items():

            weights[token] = (
                1.0
                + log(
                    (context_count + 1)
                    / (frequency + 1)
                )
            )

        return weights

    def _calculate_coverage(
        self,
        retained_context_ids: set,
        information: Dict[str, Any],
        weights: Dict[str, float],
    ) -> float:

        all_tokens = set(weights.keys())

        if not all_tokens:
            return 1.0

        retained_tokens = set()

        for context_id in retained_context_ids:

            retained_tokens.update(
                information[context_id]["tokens"]
            )

        total_weight = sum(weights.values())

        if total_weight == 0:
            return 1.0

        retained_weight = sum(
            weights[token]
            for token in retained_tokens
            if token in weights
        )

        return retained_weight / total_weight

    def _calculate_similarity_matrix(
        self,
        task_contexts: List[ContextItem],
    ):

        if self.similarity_engine is not None:

            return self.similarity_engine.build_similarity_matrix(
                task_contexts
            )

        # Fallback: calculate token-based Jaccard similarity.
        features = self.feature_extractor.extract_many(
            task_contexts
        )

        token_sets = [
            feature.tokens
            for feature in features
        ]

        count = len(token_sets)

        matrix = [
            [0.0 for _ in range(count)]
            for _ in range(count)
        ]

        for i in range(count):

            for j in range(count):

                union = token_sets[i] | token_sets[j]
                intersection = token_sets[i] & token_sets[j]

                matrix[i][j] = (
                    len(intersection) / len(union)
                    if union
                    else 0.0
                )

        return matrix

    def select(
        self,
        task_contexts: List[ContextItem],
        selected_states: List[SelectedState],
    ) -> Dict[str, Any]:

        if not task_contexts or not selected_states:

            return {
                "selected_states": [],
                "removed_context_ids": [],
                "failed_context_ids": [
                    context.context_id
                    for context in task_contexts
                ],
                "coverage": 0.0,
                "baseline_cost": 0.0,
                "total_cost": 0.0,
                "cost_reduction": 0.0,
                "context_count": len(task_contexts),
                "selected_context_count": 0,
            }

        information = self.extract_task_information(
            task_contexts
        )

        state_by_id = {
            state.context_id: state
            for state in selected_states
        }

        context_by_id = {
            context.context_id: context
            for context in task_contexts
        }

        valid_ids = [
            context.context_id
            for context in task_contexts
            if context.context_id in state_by_id
        ]

        failed_context_ids = [
            context.context_id
            for context in task_contexts
            if context.context_id not in state_by_id
        ]

        information = {
            context_id: information[context_id]
            for context_id in valid_ids
        }

        if not valid_ids:

            return {
                "selected_states": [],
                "removed_context_ids": [],
                "failed_context_ids": failed_context_ids,
                "coverage": 0.0,
                "baseline_cost": 0.0,
                "total_cost": 0.0,
                "cost_reduction": 0.0,
                "context_count": len(task_contexts),
                "selected_context_count": 0,
            }

        weights = self._calculate_information_weights(
            information
        )

        baseline_cost = sum(
            state_by_id[context_id].cost
            for context_id in valid_ids
        )

        retained_ids = set(valid_ids)

        similarity_matrix = self._calculate_similarity_matrix(
            [
                context_by_id[context_id]
                for context_id in valid_ids
            ]
        )

        # Calculate each context's strongest similarity
        # with another context.
        redundancy = {}

        for i, context_id in enumerate(valid_ids):

            similarities = [
                float(similarity_matrix[i][j])
                for j in range(len(valid_ids))
                if i != j
            ]

            redundancy[context_id] = (
                max(similarities)
                if similarities
                else 0.0
            )

        # Try the most redundant contexts first.
        removal_order = sorted(
            valid_ids,
            key=lambda context_id: (
                redundancy[context_id],
                state_by_id[context_id].cost,
            ),
            reverse=True,
        )

        removed_context_ids = []

        for context_id in removal_order:

            candidate_ids = retained_ids - {context_id}

            coverage = self._calculate_coverage(
                candidate_ids,
                information,
                weights,
            )

            if coverage >= self.coverage_threshold:

                retained_ids = candidate_ids
                removed_context_ids.append(context_id)

        final_coverage = self._calculate_coverage(
            retained_ids,
            information,
            weights,
        )

        final_states = [
            state_by_id[context_id]
            for context_id in valid_ids
            if context_id in retained_ids
        ]

        total_cost = sum(
            state.cost
            for state in final_states
        )

        cost_reduction = (
            (baseline_cost - total_cost) / baseline_cost
            if baseline_cost > 0
            else 0.0
        )

        return {
            "selected_states": final_states,
            "removed_context_ids": removed_context_ids,
            "failed_context_ids": failed_context_ids,
            "coverage": final_coverage,
            "baseline_cost": baseline_cost,
            "total_cost": total_cost,
            "cost_reduction": cost_reduction,
            "context_count": len(task_contexts),
            "selected_context_count": len(final_states),
        }