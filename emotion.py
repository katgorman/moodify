# emotion.py

from transformers import pipeline

# map many HF labels into our target mood categories
LABEL_MAP = {
    "joy": "happy",
    "happiness": "happy",
    "love": "happy",
    "surprise": "happy",
    "sadness": "sad",
    "sad": "sad",
    "anger": "angry",
    "anger/annoyance": "angry",
    "fear": "anxious",
    "anxiety": "anxious",
    "relief": "relaxed",
    "calm": "relaxed",
    "neutral": "neutral"
}

TARGET_EMOTIONS = ["happy", "sad", "relaxed", "anxious", "angry", "neutral"]

class EmotionDetector:
    def __init__(self, model_name=None):
        # default model is relatively small and good for emotion classification
        model_name = model_name or "j-hartmann/emotion-english-distilroberta-base"
        # Use return_all_scores to get probabilities for all labels
        self.pipe = pipeline("text-classification", model=model_name, return_all_scores=True, truncation=True)

    def predict(self, text: str):
        """
        Predict emotion distribution over our TARGET_EMOTIONS.
        Returns:
           {"scores": {emotion:score, ...}, "top": top_emotion_label, "top_score": top_score}
        """
        # the HF pipeline returns a list of dicts for the example: take the first element
        raw = self.pipe(text)[0]  # list of {label, score}
        # initialize zeroed distribution
        scores = {e: 0.0 for e in TARGET_EMOTIONS}
        # accumulate probabilities mapping raw labels into our target emotions
        for entry in raw:
            label = entry["label"].lower()
            score = float(entry["score"])
            mapped = LABEL_MAP.get(label, None)
            if mapped and mapped in scores:
                scores[mapped] += score
            else:
                # if unmapped label is already in our target set, add it directly
                if label in scores:
                    scores[label] += score
        # normalize
        s = sum(scores.values())
        if s > 0:
            for k in scores:
                scores[k] /= s
        # pick top
        top = max(scores.items(), key=lambda x: x[1])
        return {"scores": scores, "top": top[0], "top_score": top[1]}