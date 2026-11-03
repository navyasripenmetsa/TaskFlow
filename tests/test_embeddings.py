import json
from task_engine.normalizer import load_contexts
from task_engine.embeddings import EmbeddingEngine
with open("../data/test_session.json", "r", encoding="utf-8") as f:
    session_data = json.load(f)
contexts = load_contexts(session_data)
engine = EmbeddingEngine()
embeddings = engine.encode_contexts(contexts)
print("Number of contexts:", len(contexts))
print("Embedding shape:", embeddings.shape)
print("First embedding dimensions:", embeddings[0][:10])