# spotify_helper.py

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import numpy as np
from typing import List, Dict, Any
import math
import os

# scopes required: top tracks + recently played + playlist creation
SCOPES = "user-top-read user-read-recently-played playlist-modify-public playlist-modify-private user-library-read"

# map each high-level emotion to heuristic target audio features.
# values are approximate... you can tune per your taste.
EMOTION_TO_FEATURES = {
    "happy":    {"valence": 0.9, "energy": 0.8, "tempo": 120.0, "danceability": 0.7},
    "sad":      {"valence": 0.15, "energy": 0.25, "tempo": 70.0, "danceability": 0.25},
    "relaxed":  {"valence": 0.5, "energy": 0.35, "tempo": 75.0, "danceability": 0.35, "acousticness": 0.6},
    "anxious":  {"valence": 0.35, "energy": 0.45, "tempo": 85.0, "danceability": 0.3},
    "angry":    {"valence": 0.2, "energy": 0.95, "tempo": 140.0, "danceability": 0.5},
    "neutral":  {"valence": 0.5, "energy": 0.5, "tempo": 100.0, "danceability": 0.5}
}

def get_spotify_client():
    """
    Initialize and return a Spotipy client using environment variables or
    Streamlit secrets for SPOTIPY_CLIENT_ID / SECRET / REDIRECT_URI.
    """
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback")
    if not client_id or not client_secret:
        raise RuntimeError("SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET must be set in environment.")
    auth_manager = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, scope=SCOPES)
    return spotipy.Spotify(auth_manager=auth_manager)

# fetch user top & recent track objects
def get_user_top_and_recent_track_objects(sp: spotipy.Spotify, top_limit=30, time_range="medium_term", recent_limit=30) -> List[Dict[str,Any]]:
    """
    Returns a deduplicated list of track objects (as returned by sp.track / sp.current_user_top_tracks / sp.current_user_recently_played)
    Preference is given to top tracks, then recently played. We return up to top_limit + recent_limit unique tracks.
    """
    candidates = []
    seen_ids = set()

    # fetch top tracks
    try:
        top = sp.current_user_top_tracks(limit=top_limit, time_range=time_range)
        for t in top.get("items", []):
            if t and t.get("id") and t["id"] not in seen_ids:
                candidates.append(t)
                seen_ids.add(t["id"])
    except Exception:
        # silently ignore; try recent tracks next
        top = None

    # fetch recently played
    try:
        recent = sp.current_user_recently_played(limit=recent_limit)
        for item in recent.get("items", []):
            tr = item.get("track") if isinstance(item, dict) else None
            if tr and tr.get("id") and tr["id"] not in seen_ids:
                candidates.append(tr)
                seen_ids.add(tr["id"])
    except Exception:
        recent = None

    return candidates

# audio features fetching
def fetch_audio_features_map(sp: spotipy.Spotify, track_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    features_map = {}
    batch_size = 50

    for i in range(0, len(track_ids), batch_size):
        chunk = track_ids[i:i + batch_size]

        try:
            feats = sp.audio_features(chunk)
        except Exception as e:
            print(f"Audio feature batch failed: {e}")
            continue

        for f in feats:
            if not f or not f.get("id"):
                continue

            features_map[f["id"]] = {
                "id": f["id"],
                "valence": f.get("valence", 0.5),
                "energy": f.get("energy", 0.5),
                "tempo": f.get("tempo", 100.0),
                "danceability": f.get("danceability", 0.5),
                "acousticness": f.get("acousticness", 0.0),
                "instrumentalness": f.get("instrumentalness", 0.0),
                "liveness": f.get("liveness", 0.0),
            }

    return features_map

# build target features vector from emotion label and desired behavior
def build_target_features_from_emotion(emotion_label: str, behavior="match"):
    """
    Return a target feature dict based on emotion_label and behavior:
      - if behavior == "match": the feature target is the emotion mapping unchanged.
      - if behavior == "change": we push away from the emotion toward a 'cheer up' or 'calm down' variant.
    This is a heuristic function; tune values as desired.
    """
    base = EMOTION_TO_FEATURES.get(emotion_label, EMOTION_TO_FEATURES["neutral"]).copy()

    if behavior == "match":
        return base

    # if 'change' behavior, choose a target that shifts mood.
    # rules:
    # - if user is sad/anxious/angry: push toward 'happy' or 'relaxed'
    # - if user is happy/relaxed: push toward a slightly different optimistic/energetic variant
    if emotion_label in ("sad", "anxious", "angry"):
        # cheer up: lean toward 'happy' but keep some attributes of current emotion removed
        happy = EMOTION_TO_FEATURES["happy"]
        # blend: 30% original, 70% happy
        blended = {
            "valence": 0.3 * base["valence"] + 0.7 * happy["valence"],
            "energy": 0.3 * base["energy"] + 0.7 * happy["energy"],
            "tempo": 0.3 * base["tempo"] + 0.7 * happy["tempo"],
            "danceability": 0.3 * base.get("danceability", 0.5) + 0.7 * happy.get("danceability", 0.5)
        }
        return blended

    # if currently happy: calm down / relax slightly
    if emotion_label == "happy":
        relaxed = EMOTION_TO_FEATURES["relaxed"]
        blended = {
            "valence": 0.6 * base["valence"] + 0.4 * relaxed["valence"],
            "energy": 0.6 * base["energy"] + 0.4 * relaxed["energy"],
            "tempo": 0.6 * base["tempo"] + 0.4 * relaxed["tempo"],
            "danceability": 0.6 * base.get("danceability", 0.5) + 0.4 * relaxed.get("danceability", 0.5)
        }
        return blended

    # fallback: return neutral-ish shift
    neutral = EMOTION_TO_FEATURES["neutral"]
    blended = {
        "valence": 0.5 * base["valence"] + 0.5 * neutral["valence"],
        "energy": 0.5 * base["energy"] + 0.5 * neutral["energy"],
        "tempo": 0.5 * base["tempo"] + 0.5 * neutral["tempo"],
        "danceability": 0.5 * base.get("danceability", 0.5) + 0.5 * neutral.get("danceability", 0.5)
    }
    return blended


# scoring & sampling
def _feature_vector_from_feat_dict(feat_dict: Dict[str,Any]):
    """
    Convert feature dict into a numeric vector for distance calculations.
    We'll normalize tempo into 0..1 by dividing by 200 (reasonable upper bound).
    Order: [valence, energy, tempo_norm, danceability]
    """
    return np.array([
        feat_dict.get("valence", 0.5),
        feat_dict.get("energy", 0.5),
        feat_dict.get("tempo", 100.0) / 200.0,
        feat_dict.get("danceability", 0.5)
    ], dtype=float)

def score_and_sample_tracks(features_list: List[Dict[str,Any]], k=10, target: Dict[str,float]=None, seed=None):
    """
    - features_list: list of audio feature dicts (each must include 'id' and fields used)
    - target: dict with same keys (valence, energy, tempo, danceability)
    Returns: list of sampled indices (indices refer to features_list order)
    Method:
      - compute Euclidean distance from each candidate to target vector
      - convert distances to softmax probabilities (smaller distance => larger prob)
      - sample k unique indices according to probabilities
    """
    if not features_list:
        return []

    if seed is not None:
        np.random.seed(seed)

    target_vec = np.array([target.get("valence",0.5), target.get("energy",0.5), target.get("tempo",100.0)/200.0, target.get("danceability",0.5)])
    data = np.array([_feature_vector_from_feat_dict(f) for f in features_list])

    # compute distances
    dists = np.linalg.norm(data - target_vec[np.newaxis, :], axis=1)
    # convert to scores (smaller dist -> higher score). Use a temperature-like scaling to control randomness.
    # scale = median(dists) so distances larger than median get low weights.
    scale = max(np.median(dists), 1e-6)
    scores = np.exp(-dists / (scale * 0.9))  # 0.9 to sharpen slightly
    probs = scores / np.sum(scores)

    # if fewer than k candidates, just return all indices
    n = len(features_list)
    k_choose = min(k, n)
    # sample without replacement
    chosen = np.random.choice(n, size=k_choose, replace=False, p=probs)
    return list(chosen)


# playlist creation & helpers
def create_playlist_and_add_tracks(sp: spotipy.Spotify, user_id: str, name: str, track_uris: List[str], description: str = ""):
    """
    Create a playlist for the user and add the provided track URIs.
    Accepts either URIs like "spotify:track:<id>" or track IDs; we'll convert IDs to URIs when needed.
    """
    # normalize URIs
    prepared = []
    for t in track_uris:
        if not t:
            continue
        if isinstance(t, str) and t.startswith("spotify:track:"):
            prepared.append(t)
        elif isinstance(t, str) and len(t) == 22:
            prepared.append(f"spotify:track:{t}")
        elif isinstance(t, str) and "open.spotify.com/track/" in t:
            try:
                tid = t.split("track/")[1].split("?")[0]
                prepared.append(f"spotify:track:{tid}")
            except Exception:
                prepared.append(t)
        else:
            prepared.append(t)

    # create playlist (private by default)
    pl = sp.user_playlist_create(user=user_id, name=name, public=False, description=description or "")
    # add in chunks of 100
    for i in range(0, len(prepared), 100):
        chunk = prepared[i:i+100]
        sp.playlist_add_items(playlist_id=pl["id"], items=chunk)
    return pl

def explain_track_features(track_obj: Dict, emotion=None) -> Dict:
    """
    Build a small dict for UI display. track_obj is Spotify track object.
    """
    return {
        "name": track_obj.get("name"),
        "artists": ", ".join([a.get("name") for a in track_obj.get("artists", [])]) if track_obj.get("artists") else "",
        "id": track_obj.get("id"),
        "uri": track_obj.get("uri"),
        "preview_url": track_obj.get("preview_url"),
        "popularity": track_obj.get("popularity"),
        "related_emotion": emotion
    }