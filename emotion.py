# emotion.py
from transformers import pipeline

LABEL_MAP = {
    "joy": "happy",
    "happiness": "happy",
    "sadness": "sad",
    "anger": "angry",
    "anger/annoyance": "angry",
    "fear": "anxious",
    "anxiety": "anxious",
    "relief": "relaxed",
    "calm": "relaxed",
}

TARGET_EMOTIONS = ["happy", "sad", "relaxed", "anxious", "angry"]

class EmotionDetector:
    def __init__(self, model_name=None):
        model_name = model_name or "j-hartmann/emotion-english-distilroberta-base"
        self.pipe = pipeline("text-classification", model=model_name, return_all_scores=True, truncation=True)

    def predict(self, text):
        raw = self.pipe(text)[0]  # list of {label, score}
        scores = {e: 0.0 for e in TARGET_EMOTIONS}
        for entry in raw:
            label = entry["label"].lower()
            score = float(entry["score"])
            mapped = LABEL_MAP.get(label, None)
            if mapped in scores:
                scores[mapped] += score
            elif label in scores:
                scores[label] += score
        # normalize
        s = sum(scores.values())
        if s > 0:
            for k in scores:
                scores[k] /= s
        top = max(scores.items(), key=lambda x: x[1])
        return {"scores": scores, "top": top[0], "top_score": top[1]}