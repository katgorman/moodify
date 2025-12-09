from ollama import Client

TARGET_EMOTIONS = ["happy", "sad", "relaxed", "anxious", "angry", "neutral"]

class EmotionDetector:
    def __init__(self, model_name="llama3.2:1b"):
        self.client = Client()
        self.model_name = model_name

    def detect_current_mood(self, text: str):
        # prompt the model to classify user-stated mood
        resp = self.client.generate(
            model=self.model_name,
            prompt=(
                "You are a rule-based emotion classifier.\n\nThe user is directly describing THEIR CURRENT MOOD in plain language.\n\nCLASSIFY ONLY ONE MOOD from this fixed list:\nhappy, sad, relaxed, anxious, angry, neutral\n\nRULES:\n- Output ONLY the mood word, all lowercase.\n- No sentences, no punctuation, no explanation.\n- If multiple moods are implied, choose the most explicit one.\n- If the text describes physical tension, fear, worry, or stress → anxious.\n- If the text contains words like upset, pissed, irritated → angry.\n- If the mood is unclear or mixed → neutral.\n\nUser text:\n\"{text}\"\n\nAnswer with only one word from the list."

            )
        )
        # resp.response contains the text output
        mood = resp.response.strip().lower()
        if mood not in TARGET_EMOTIONS:
            mood = "neutral"
        return mood

    def predict(self, text: str):
        return {"top": self.detect_current_mood(text)}
