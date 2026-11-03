from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer

from .models import ContextItem


class EmbeddingEngine:
    def __init__(self, model_name: str = "sentence-transformers/all-mpnet-base-v2"):
        self.model = SentenceTransformer(model_name)

    def context_text(self, context: ContextItem) -> str:
        """
        Convert a context item into semantic text for embedding.
        """
        return (
            f"Title: {context.title}\n"
            f"Domain: {context.domain}\n"
            f"Content: {context.text}"
        )

    def encode_contexts(
        self,
        contexts: List[ContextItem]
    ) -> np.ndarray:
        """
        Generate one embedding vector for each context item.
        """
        texts = [self.context_text(context) for context in contexts]

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        return embeddings

    def encode_text(self, text: str) -> np.ndarray:
        """
        Generate an embedding for an arbitrary piece of text.
        Used later for task requirements.
        """
        return self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True
        )