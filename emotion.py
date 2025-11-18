# emotion.py
from transformers import pipeline

# Choose a compact emotion model (examples exist on Hugging Face).
# Keep it configurable; the baseline uses pipeline("text-classification", model=...) with
# return_all_scores=True so we can map to the 5 target emotions.

# Map model emotion labels (model-dependent) to our 5 target emotions:
LABEL_MAP = {
    # Example mapping — adapt if your model uses different labels
    "joy": "happy",
    "happiness": "happy",
    "sadness": "sad",
    "anger": "angry",
    "anger/annoyance": "angry",
    "fear": "anxious",
    "anxiety": "anxious",
    "relief": "relaxed",
    "calm": "relaxed",
    # fallback: keep as-is
}

TARGET_EMOTIONS = ["happy", "sad", "relaxed", "anxious", "angry"]

class EmotionDetector:
    def __init__(self, model_name=None):
        # If model_name is None, pipeline will pick a default model if available locally
        # For reliability, pass an explicit small model (e.g., "j-hartmann/emotion-english-distilroberta-base")
        model_name = model_name or "j-hartmann/emotion-english-distilroberta-base"
        self.pipe = pipeline("text-classification", model=model_name, return_all_scores=True, truncation=True)

    def predict(self, text):
        """
        Returns a dict of target_emotion -> score (0..1) and the top predicted label.
        """
        raw = self.pipe(text)[0]  # list of {label, score}
        # aggregate into our 5-target emotions
        scores = {e: 0.0 for e in TARGET_EMOTIONS}
        for entry in raw:
            label = entry["label"].lower()
            score = float(entry["score"])
            mapped = LABEL_MAP.get(label, None)
            if mapped in scores:
                scores[mapped] += score
            else:
                # If the label matches one of our targets directly (model might already use them)
                if label in scores:
                    scores[label] += score
                # otherwise ignore or optionally distribute
        # normalize so they sum to 1 (if nonzero)
        s = sum(scores.values())
        if s > 0:
            for k in scores:
                scores[k] /= s
        # top emotion
        top = max(scores.items(), key=lambda x: x[1])
        return {"scores": scores, "top": top[0], "top_score": top[1]}
