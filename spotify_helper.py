# spotify_helper.py
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

EMOTION_FEATURES = {
    "happy":    {"target_valence": 0.9, "target_energy": 0.85, "min_tempo": 100, "max_tempo": 160},
    "sad":      {"target_valence": 0.15, "target_energy": 0.2,  "min_tempo": 50,  "max_tempo": 90},
    "relaxed":  {"target_valence": 0.5, "target_energy": 0.3,  "min_tempo": 60,  "max_tempo": 110, "target_acousticness": 0.7},
    "anxious":  {"target_valence": 0.4, "target_energy": 0.5,  "min_tempo": 80,  "max_tempo": 140, "target_danceability": 0.3},
    "angry":    {"target_valence": 0.1, "target_energy": 0.95, "min_tempo": 90,  "max_tempo": 160, "target_loudness": -5.0},
}

SCOPE = "playlist-modify-private playlist-modify-public user-read-private"

def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE))

def build_recommendation_params(emotion, seed_tracks=None, change_mood=False):
    params = {}
    features = EMOTION_FEATURES.get(emotion, {})
    params.update(features)

    if change_mood and "target_valence" in params:
        params["target_valence"] = 1.0 - params["target_valence"]

    if seed_tracks:
        params["seed_tracks"] = seed_tracks[:5]
    else:
        params["seed_genres"] = ["pop", "indie", "rock"]

    params["limit"] = 20
    return params

def recommend_tracks(sp, emotion, seed_tracks=None, change_mood=False):
    # Build audio feature targets
    params = build_recommendation_params(emotion, seed_tracks, change_mood)

    # use seed tracks, never seed genres
    # If user didn’t give any seeds, choose stable global hits
    if seed_tracks:
        seeds = seed_tracks[:5]
    else:
        # Get 3 globally popular tracks guaranteed to exist
        global_hits = sp.search(q="year:2024", type="track", limit=3)
        seeds = [t["id"] for t in global_hits["tracks"]["items"]]

    # Build allowed params
    allowed = [
        "limit",
        "min_tempo",
        "max_tempo",
        "target_valence",
        "target_energy",
        "target_danceability",
        "target_acousticness",
        "target_loudness",
    ]

    feature_params = {k: v for k, v in params.items() if k in allowed}

    # Final recommendation call
    rec_params = {
        "limit": 20,
        "seed_tracks": seeds,
        **feature_params
    }

    try:
        results = sp.recommendations(**rec_params)
    except:
        # Absolute fallback
        results = sp.recommendations(
            limit=20,
            seed_tracks=seeds
        )

    # Build track list
    tracks = []
    ids = []

    for t in results["tracks"]:
        tid = t["id"]
        ids.append(tid)
        tracks.append({
            "id": tid,
            "name": t["name"],
            "artists": ", ".join(a["name"] for a in t["artists"]),
            "uri": t["uri"],
            "preview_url": t.get("preview_url")
        })

    # Get audio features
    audio_features = sp.audio_features(ids)
    for track, feats in zip(tracks, audio_features):
        track["features"] = feats

    return tracks

# generate explanation text from real audio features
def explain_track_features(track, target_emotion):
    feats = track["features"]
    if not feats:
        return "No audio feature data available."

    valence = feats.get("valence")
    energy = feats.get("energy")
    dance = feats.get("danceability")
    acoustic = feats.get("acousticness")
    tempo = feats.get("tempo")
    loud = feats.get("loudness")

    explanation = []

    explanation.append(f"Valence {valence:.2f} — {'positive/uplifting' if valence > 0.6 else 'moody/low'}")
    explanation.append(f"Energy {energy:.2f} — {'high intensity' if energy > 0.6 else 'calmer'}")
    explanation.append(f"Tempo {tempo:.0f} BPM")
    explanation.append(f"Danceability {dance:.2f}")
    explanation.append(f"Acousticness {acoustic:.2f}")
    explanation.append(f"Loudness {loud:.1f} dB")

    # emotion-specific reasoning layer
    if target_emotion == "happy":
        explanation.append("→ This matches *happy* because of high valence and energy.")
    elif target_emotion == "sad":
        explanation.append("→ This fits *sad* due to lower valence and softer loudness.")
    elif target_emotion == "relaxed":
        explanation.append("→ Suitable for *relaxed* mood with acousticness and moderate tempo.")
    elif target_emotion == "anxious":
        explanation.append("→ Helps with *anxious* states via moderate energy and rhythmic stability.")
    elif target_emotion == "angry":
        explanation.append("→ Fits *angry* mood due to high energy and loudness.")

    return " | ".join(explanation)

def create_playlist_and_add_tracks(sp, user_id, name, track_uris, public=False, description=""):
    playlist = sp.user_playlist_create(user=user_id, name=name, public=public, description=description)
    sp.playlist_add_items(playlist["id"], track_uris)
    return playlist
