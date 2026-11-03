from typing import List
from collections import Counter
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
import numpy as np
import yake

from .models import ContextItem, TaskCandidate
from .embeddings import EmbeddingEngine
from .similarity import ContextSimilarityEngine
from .task_label_generator import TaskLabelGenerator


class TaskInferenceEngine:

    def __init__(
        self,
        embedding_engine: EmbeddingEngine,
        similarity_engine: ContextSimilarityEngine | None = None,
        merge_threshold: float = 0.35,
        coherence_threshold: float = 0.30,
    ):
        self.embedding_engine = embedding_engine

        self.similarity_engine = (
            similarity_engine
            if similarity_engine is not None
            else ContextSimilarityEngine(embedding_engine)
        )

        self.merge_threshold = merge_threshold
        self.coherence_threshold = coherence_threshold
        self.coherence_threshold = max(
            coherence_threshold,
            0.40,
        )
        # Local keyphrase extraction.
        self.keyword_extractor = yake.KeywordExtractor(
            lan="en",
            n=3,
            dedupLim=0.7,
            top=40,
        )

        # LLM is optional. Its failure must not stop task discovery.
        try:
            self.label_generator = TaskLabelGenerator()
        except Exception as error:
            self.label_generator = None
            print(
                f"LLM labeling unavailable. "
                f"Using local fallback: {error}"
            )

    def discover_tasks(
        self,
        contexts: List[ContextItem],
    ) -> List[TaskCandidate]:

        if not contexts:
            return []

        # 1. Calculate composite similarity locally.
        similarity_matrix = (
            self.similarity_engine.build_similarity_matrix(contexts)
        )
        print("\nPAIRWISE SIMILARITIES:")

        for i in range(len(contexts)):
            for j in range(i + 1, len(contexts)):
                print(
                    f"{contexts[i].context_id} - "
                    f"{contexts[j].context_id}: "
                    f"{similarity_matrix[i, j]:.3f}"
                )

                # 2. Adaptive average-link agglomerative clustering.

        # Convert similarity into distance.
        distance_matrix = 1.0 - similarity_matrix
        distance_matrix = np.clip(distance_matrix, 0.0, 1.0)
        np.fill_diagonal(distance_matrix, 0.0)

        context_count = len(contexts)

        if context_count == 1:
            cluster_indices = [[0]]

        else:
            best_score = float("-inf")
            best_labels = None

            # Evaluate possible cluster counts.
            # Silhouette requires at least 2 clusters and
            # fewer clusters than the number of contexts.
            for k in range(2, context_count):

                clustering = AgglomerativeClustering(
                    n_clusters=k,
                    metric="precomputed",
                    linkage="average",
                )

                labels = clustering.fit_predict(distance_matrix)

                score = silhouette_score(
                    distance_matrix,
                    labels,
                    metric="precomputed",
                )

                print(
                    f"Clustering with {k} groups: "
                    f"silhouette={score:.3f}"
                )

                if score > best_score:
                    best_score = score
                    best_labels = labels

            # If no useful separation is found, retain
            # one group rather than forcing a split.
            if best_labels is None or best_score <= 0:
                cluster_indices = [
                    list(range(context_count))
                ]

            else:
                cluster_indices = []

                for cluster_id in sorted(set(best_labels)):
                    members = [
                        index
                        for index, label in enumerate(best_labels)
                        if label == cluster_id
                    ]

                    cluster_indices.append(members)

        # Convert index groups into context groups.
        clusters = [
            [contexts[index] for index in members]
            for members in cluster_indices
        ]

        print(
            f"Selected {len(clusters)} task groups "
            f"using adaptive hierarchical clustering."
        )
        # 3. Interpret each discovered group.
        tasks = []

        for task_number, cluster_contexts in enumerate(
            clusters,
            start=1,
        ):

            coherence = self._cluster_coherence(
                cluster_contexts,
                contexts,
                similarity_matrix,
            )

            tasks.append(
                self._create_task_candidate(
                    cluster_contexts,
                    task_number,
                    coherence,
                )
            )

        return tasks

    def _cluster_coherence(
        self,
        cluster_contexts: List[ContextItem],
        all_contexts: List[ContextItem],
        similarity_matrix: np.ndarray,
    ) -> float:

        if len(cluster_contexts) <= 1:
            return 1.0

        indices = [
            all_contexts.index(context)
            for context in cluster_contexts
        ]

        scores = []

        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):

                scores.append(
                    float(
                        similarity_matrix[
                            indices[i],
                            indices[j],
                        ]
                    )
                )

        if not scores:
            return 1.0

        return float(np.mean(scores))

    # --------------------------------------------------
    # LOCAL GROUP FEATURE EXTRACTION
    # --------------------------------------------------

    def _extract_context_keyphrases(
        self,
        context: ContextItem,
    ) -> List[str]:
        """
        Extract keyphrases locally from one context.

        Raw text is used only inside the local backend.
        It is not passed directly to the LLM.
        """

        source_text = " ".join([
            context.title or "",
            context.domain or "",
            (context.text or "")[:4000],
        ]).strip()

        if not source_text:
            return []

        extracted = self.keyword_extractor.extract_keywords(
            source_text
        )

        phrases = []
        seen = set()

        for phrase, _score in extracted:

            phrase = " ".join(phrase.split()).strip()
            normalized = phrase.casefold()

            if phrase and normalized not in seen:
                seen.add(normalized)
                phrases.append(phrase)

            if len(phrases) >= 5:
                break

        return phrases

    def _build_group_summary(
        self,
        contexts: List[ContextItem],
    ) -> dict:
        """
        Construct compact group-level features locally.

        Does not include raw page text, titles, URLs, domains,
        form values, or interaction state.
        """

        context_signals = []
        phrase_counts = Counter()
        phrase_display = {}

        for index, context in enumerate(contexts, start=1):

            phrases = self._extract_context_keyphrases(context)

            context_signals.append({
                "context_number": index,
                "keyphrases": phrases,
            })

            for phrase in phrases:
                normalized = phrase.casefold()
                phrase_counts[normalized] += 1
                phrase_display.setdefault(normalized, phrase)

        repeated_keyphrases = [
            phrase_display[normalized]
            for normalized, count in phrase_counts.most_common()
            if count >= 2
        ][:10]

        return {
            "context_count": len(contexts),
            "repeated_keyphrases": repeated_keyphrases,
            "context_signals": context_signals,
        }

    # --------------------------------------------------
    # TASK CANDIDATE CREATION
    # --------------------------------------------------

    def _create_task_candidate(
        self,
        contexts: List[ContextItem],
        task_number: int,
        coherence: float,
    ) -> TaskCandidate:

        context_ids = [
            context.context_id
            for context in contexts
        ]

        # Prepare local fallback first.
        label = self._generate_task_label(contexts)
        description = self._generate_task_description(contexts)

        # LLM receives only the compact group summary.
        if self.label_generator is not None:

            try:
                group_summary = self._build_group_summary(contexts)

                task_info = self.label_generator.generate(
                    group_summary
                )

                label = task_info["task_label"]
                description = task_info["task_goal"]

                print(
                    f"Task label confidence: "
                    f"{task_info['confidence']:.2f}"
                )

            except Exception as error:
                print(
                    "LLM labeling failed. "
                    f"Using local fallback: {error}"
                )

        return TaskCandidate(
            task_id=f"task_{task_number:03d}",
            context_ids=context_ids,
            label=label,
            description=description,
            coherence=coherence,
        )

    # --------------------------------------------------
    # LOCAL FALLBACK LABEL GENERATION
    # --------------------------------------------------

    def _generate_task_label(
        self,
        contexts: List[ContextItem],
    ) -> str:

        if not contexts:
            return "Unknown task"

        task_documents = []

        for context in contexts:

            document = (
                f"{context.title or ''}\n"
                f"{context.domain or ''}\n"
                f"{(context.text or '')[:4000]}"
            )

            if document.strip():
                task_documents.append(document)

        combined_text = "\n\n".join(task_documents)

        if not combined_text.strip():
            return self._fallback_task_label(contexts)

        extracted_keywords = (
            self.keyword_extractor.extract_keywords(combined_text)
        )

        if not extracted_keywords:
            return self._fallback_task_label(contexts)

        candidates = []
        seen = set()

        for phrase, yake_score in extracted_keywords:

            phrase = phrase.strip()
            normalized_phrase = phrase.casefold()

            if not phrase or normalized_phrase in seen:
                continue

            seen.add(normalized_phrase)
            candidates.append((phrase, float(yake_score)))

        if not candidates:
            return self._fallback_task_label(contexts)

        context_embeddings = (
            self.embedding_engine.encode_contexts(contexts)
        )

        task_embedding = np.mean(context_embeddings, axis=0)
        task_norm = np.linalg.norm(task_embedding)

        if task_norm == 0:
            return self._fallback_task_label(contexts)

        task_embedding = task_embedding / task_norm

        yake_scores = [
            score for _, score in candidates
        ]

        max_yake_score = max(yake_scores)
        ranked_candidates = []

        for phrase, yake_score in candidates:

            phrase_embedding = (
                self.embedding_engine.encode_text(phrase)
            )

            semantic_similarity = float(
                np.dot(task_embedding, phrase_embedding)
            )

            semantic_relevance = (
                semantic_similarity + 1.0
            ) / 2.0

            keyword_relevance = (
                1.0 - yake_score / (max_yake_score + 1e-9)
            )

            final_score = (
                0.80 * semantic_relevance
                + 0.20 * keyword_relevance
            )

            ranked_candidates.append(
                (phrase, final_score)
            )

        ranked_candidates.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        return ranked_candidates[0][0].title()

    def _fallback_task_label(
        self,
        contexts: List[ContextItem],
    ) -> str:

        if not contexts:
            return "Unknown task"

        representative = max(
            contexts,
            key=lambda context: len(
                (context.title or "").split()
            ),
        )

        return (
            representative.title
            or "Task involving multiple contexts"
        )

    def _generate_task_description(
        self,
        contexts: List[ContextItem],
    ) -> str:

        if not contexts:
            return "Unknown task"

        titles = [
            context.title
            for context in contexts
        ]

        return (
            "Task involving: "
            + "; ".join(titles)
        )
