import json

from task_engine.normalizer import load_contexts
from task_engine.embeddings import EmbeddingEngine
from task_engine.similarity import ContextSimilarityEngine


with open(
    "data/test_session.json",
    "r",
    encoding="utf-8",
) as f:

    session_data = json.load(f)


contexts = load_contexts(
    session_data
)

embedding_engine = EmbeddingEngine()

similarity_engine = ContextSimilarityEngine(
    embedding_engine
)

matrix = similarity_engine.build_similarity_matrix(
    contexts
)


print()
print("SIMILARITY MATRIX")
print("=================")

print(
    "Shape:",
    matrix.shape
)

for i, context in enumerate(contexts):

    print(
        context.context_id,
        "->",
        [
            round(float(value), 3)
            for value in matrix[i]
        ]
    )