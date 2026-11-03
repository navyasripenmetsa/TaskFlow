import json

from task_engine.features import FeatureExtractor
from task_engine.normalizer import load_contexts


with open("data/test_session.json", "r", encoding="utf-8") as file:
    session_data = json.load(file)


contexts = load_contexts(session_data)

extractor = FeatureExtractor()
features = extractor.extract_many(contexts)

print("\nFEATURE EXTRACTION TEST")
print("=======================")

for feature in features:
    print(f"\nContext: {feature.context_id}")
    print(f"Active: {feature.active}")
    print(f"Timestamp: {feature.timestamp}")
    print(f"Tokens: {sorted(feature.tokens)}")