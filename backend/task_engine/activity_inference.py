
from typing import List, Optional

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

from .models import TaskCandidate, ActivityCandidate, ContextItem
from .embeddings import EmbeddingEngine
from .task_label_generator import TaskLabelGenerator


class ActivityInferenceEngine:

    def __init__(
        self,
        embedding_engine: EmbeddingEngine | None = None,
    ):
        self.embedding_engine = (
            embedding_engine
            if embedding_engine is not None
            else EmbeddingEngine()
        )

        try:
            self.label_generator = TaskLabelGenerator()
        except Exception as error:
            self.label_generator = None
            print(
                "Activity labeling unavailable. "
                f"Using local fallback: {error}"
            )

        self.task_evidence = {}

    # --------------------------------------------------
    # CONTEXT EVIDENCE
    # --------------------------------------------------

    def _build_task_evidence(
        self,
        tasks: List[TaskCandidate],
        contexts: Optional[List[ContextItem]],
    ) -> None:

        context_lookup = {
            context.context_id: context
            for context in (contexts or [])
        }

        self.task_evidence = {}

        for task in tasks:

            evidence_parts = []

            for context_id in task.context_ids:

                context = context_lookup.get(context_id)

                if context is None:
                    continue

                # Use content that can help identify the broader goal.
                evidence_parts.extend([
                    context.title or "",
                    context.domain or "",
                    context.url or "",
                    (context.text or "")[:3000],
                ])

            self.task_evidence[task.task_id] = " ".join(
                evidence_parts
            )

    # --------------------------------------------------
    # TASK REPRESENTATION
    # --------------------------------------------------

    def _task_text(self, task: TaskCandidate) -> str:

        return " ".join([
            task.label or "",
            task.description or "",
            self.task_evidence.get(task.task_id, ""),
        ]).strip()

    # --------------------------------------------------
    # BROADER GOAL INFERENCE
    # --------------------------------------------------

    def _infer_task_goal(self, task: TaskCandidate) -> str:

        # Only the compact task label and description are sent to NVIDIA.
        # Raw browser context remains local.

        if self.label_generator is None:
            return f"{task.label}: {task.description}"

        try:

            result = self.label_generator.generate_activity({
                "task_count": 1,
                "task_signals": [{
                    "task_label": task.label,
                    "task_description": task.description,
                }],
            })

            return result["task_goal"]

        except Exception as error:

            print(
                f"Goal inference failed for {task.task_id}: {error}"
            )

            return self._task_text(task)

    # --------------------------------------------------
    # TASK SIMILARITY
    # --------------------------------------------------

    def _build_similarity_matrix(
        self,
        tasks: List[TaskCandidate],
        goals: List[str],
    ) -> np.ndarray:

        count = len(tasks)

        if count == 0:
            return np.empty((0, 0))

        documents = [
            self._task_text(task) + " " + goals[index]
            for index, task in enumerate(tasks)
        ]

        embeddings = np.array([
            self.embedding_engine.encode_text(document)
            for document in documents
        ])

        norms = np.linalg.norm(
            embeddings,
            axis=1,
            keepdims=True,
        )

        normalized = embeddings / np.maximum(norms, 1e-12)

        semantic = np.clip(
            normalized @ normalized.T,
            0.0,
            1.0,
        )

        np.fill_diagonal(semantic, 1.0)

        return semantic

    # --------------------------------------------------
    # ADAPTIVE ACTIVITY CLUSTERING
    # --------------------------------------------------

    def _cluster_tasks(
        self,
        similarity_matrix: np.ndarray,
    ) -> List[List[int]]:

        task_count = similarity_matrix.shape[0]

        if task_count == 0:
            return []

        if task_count == 1:
            return [[0]]

        if task_count == 2:
            # Silhouette-based selection is not meaningful
            # for two tasks, so retain them in one activity.
            return [[0, 1]]

        # Convert similarity into distance.
        distance_matrix = np.clip(
            1.0 - similarity_matrix,
            0.0,
            1.0,
        )

        np.fill_diagonal(distance_matrix, 0.0)

        best_score = float("-inf")
        best_labels = None

        # Evaluate possible cluster counts automatically.
        # No manually fixed similarity threshold is used.
        for k in range(2, task_count):

            try:
                try:
                    model = AgglomerativeClustering(
                        n_clusters=k,
                        metric="precomputed",
                        linkage="average",
                    )

                except TypeError:
                    # Compatibility with older scikit-learn versions.
                    model = AgglomerativeClustering(
                        n_clusters=k,
                        affinity="precomputed",
                        linkage="average",
                    )

                labels = model.fit_predict(distance_matrix)

                unique_labels = set(labels)

                # Silhouette requires at least two clusters
                # and fewer clusters than data samples.
                if len(unique_labels) < 2:
                    continue

                if len(unique_labels) >= task_count:
                    continue

                score = silhouette_score(
                    distance_matrix,
                    labels,
                    metric="precomputed",
                )

                print(
                    f"Activity clustering: "
                    f"k={k}, silhouette={score:.3f}"
                )

                if score > best_score:
                    best_score = score
                    best_labels = labels

            except Exception as error:
                print(
                    f"Clustering k={k} failed: {error}"
                )

        # Fallback if no valid partition can be evaluated.
        if best_labels is None:
            return [list(range(task_count))]

        clusters = [
            [
                index
                for index, label in enumerate(best_labels)
                if label == cluster_label
            ]
            for cluster_label in sorted(set(best_labels))
        ]

        return clusters

    # --------------------------------------------------
    # ACTIVITY DISCOVERY
    # --------------------------------------------------

    def discover_activities(
        self,
        tasks: List[TaskCandidate],
        contexts: Optional[List[ContextItem]] = None,
    ) -> List[ActivityCandidate]:

        if not tasks:
            return []

        self._build_task_evidence(tasks, contexts)

        if len(tasks) == 1:
            return [
                self._create_activity(tasks, 1)
            ]

        print("\nINFERRING BROADER TASK GOALS:")

        goals = []

        for task in tasks:

            goal = self._infer_task_goal(task)
            goals.append(goal)

            print(f"{task.label}: {goal}")

        similarity_matrix = self._build_similarity_matrix(
            tasks,
            goals,
        )

        print("\nTASK GOAL SIMILARITIES:")

        for i in range(len(tasks)):
            for j in range(i + 1, len(tasks)):

                print(
                    f"{tasks[i].label} - "
                    f"{tasks[j].label}: "
                    f"{similarity_matrix[i, j]:.3f}"
                )

        # Automatically determine the activity clusters.
        clusters = self._cluster_tasks(similarity_matrix)

        print(
            f"\nDYNAMIC CLUSTERING SELECTED "
            f"{len(clusters)} ACTIVITIES."
        )

        activities = []

        for number, cluster in enumerate(clusters, start=1):

            cluster_tasks = [
                tasks[index]
                for index in cluster
            ]

            activities.append(
                self._create_activity(
                    cluster_tasks,
                    number,
                )
            )

        return activities

    # --------------------------------------------------
    # ACTIVITY CREATION
    # --------------------------------------------------

    def _create_activity(
        self,
        tasks: List[TaskCandidate],
        activity_number: int,
    ) -> ActivityCandidate:

        label = "Related activities"

        description = (
            "Continue the related tasks in this activity."
        )

        if self.label_generator is not None:

            try:

                result = self.label_generator.generate_activity(
                    self._build_activity_summary(tasks)
                )

                label = result["task_label"]
                description = result["task_goal"]

                print(
                    f"Activity label confidence: "
                    f"{result['confidence']:.2f}"
                )

            except Exception as error:

                print(
                    f"Activity labeling failed: {error}"
                )

                label, description = (
                    self._fallback_activity_details(tasks)
                )

        else:

            label, description = (
                self._fallback_activity_details(tasks)
            )

        task_ids = [
            task.task_id
            for task in tasks
        ]

        context_ids = list(dict.fromkeys(
            context_id
            for task in tasks
            for context_id in task.context_ids
        ))

        coherence = self._calculate_coherence(tasks)

        return ActivityCandidate(
            activity_id=f"activity_{activity_number:03d}",
            label=label,
            description=description,
            task_ids=task_ids,
            context_ids=context_ids,
            coherence=coherence,
        )

    # --------------------------------------------------
    # ACTIVITY SUMMARY
    # --------------------------------------------------

    def _build_activity_summary(
        self,
        tasks: List[TaskCandidate],
    ) -> dict:

        return {
            "task_count": len(tasks),
            "task_signals": [
                {
                    "task_label": task.label,
                    "task_description": task.description,
                }
                for task in tasks
            ],
        }

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------

    def _fallback_activity_details(
        self,
        tasks: List[TaskCandidate],
    ) -> tuple:

        labels = [
            task.label
            for task in tasks
        ]

        return (
            "Related activities",
            "Continue these related tasks: "
            + "; ".join(labels),
        )

    # --------------------------------------------------
    # COHERENCE
    # --------------------------------------------------

    def _calculate_coherence(
        self,
        tasks: List[TaskCandidate],
    ) -> float:

        if len(tasks) <= 1:
            return 1.0

        # Coherence uses the same enriched task evidence.
        documents = [
            self._task_text(task)
            for task in tasks
        ]

        embeddings = np.array([
            self.embedding_engine.encode_text(document)
            for document in documents
        ])

        norms = np.linalg.norm(
            embeddings,
            axis=1,
            keepdims=True,
        )

        normalized = embeddings / np.maximum(norms, 1e-12)

        matrix = np.clip(
            normalized @ normalized.T,
            0.0,
            1.0,
        )

        scores = [
            matrix[i, j]
            for i in range(len(tasks))
            for j in range(i + 1, len(tasks))
        ]

        return float(np.mean(scores)) if scores else 1.0
