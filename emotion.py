from ollama import Client

TARGET_EMOTIONS = ["happy", "sad", "relaxed", "anxious", "angry", "neutral"]

class EmotionDetector:
    def __init__(self, model_name="mistral:7b"):
        self.client = Client()
        self.model_name = model_name

    def detect_current_mood(self, text: str):
        # prompt the model to classify user-stated mood
        resp = self.client.generate(
            model=self.model_name,
            prompt= (
                "You are a classifier. Read the user's text and choose exactly ONE mood from "
                "[happy, sad, relaxed, anxious, angry, neutral].\n"
                "\n"
                "The user is describing their own emotional state. You are classifying the user's mood.\n"
                "Rules:\n"
                "- Output only the mood word.\n"
                "- Lowercase.\n"
                "- No punctuation.\n"
                "- No explanations.\n"
                "\n"
                "User text: \"{text}\"\n"
                "Answer:"
            )

        )
        # resp.response contains the text output
        mood = resp.response.strip().lower()
        if mood not in TARGET_EMOTIONS:
            mood = "neutral"
        return mood

    def predict(self, text: str):
        return {"top": self.detect_current_mood(text)}
