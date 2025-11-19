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
    """Return an authenticated Spotify client."""
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE))


def normalize_ids(seeds):
    """
    Convert a list of track dicts or strings into a list of track IDs.
    """
    cleaned = []
    for s in seeds:
        if isinstance(s, dict) and "id" in s:
            cleaned.append(s["id"])
        elif isinstance(s, str):
            cleaned.append(s)
    return cleaned


def recommend_tracks(sp, top_tracks=None, seed_tracks=None, change_mood=None):
    """
    Return recommended tracks using valid Spotify seeds.
    Falls back to default genres if no valid track IDs exist.
    """
    # Normalize seeds
    seeds = normalize_ids(seed_tracks or top_tracks or [])[:5]
    seeds = [s for s in seeds if isinstance(s, str) and len(s) >= 10]

    # If no valid seeds, fallback to genres
    if not seeds:
        return sp.recommendations(
            limit=20,
            seed_genres=["pop", "indie", "rock"],
            **(EMOTION_FEATURES.get(change_mood, {}))
        )

    mood_kwargs = {}
    if change_mood in EMOTION_FEATURES:
        mood_kwargs.update(EMOTION_FEATURES[change_mood])

    return sp.recommendations(
        limit=20,
        seed_tracks=seeds,
        **mood_kwargs
    )


def create_playlist_and_add_tracks(sp, user_id, playlist_name, track_ids, public=False, description=""):
    """
    Create a playlist and add tracks.
    Returns the playlist object.
    """
    playlist = sp.user_playlist_create(
        user=user_id,
        name=playlist_name,
        public=public,
        description=description
    )
    sp.playlist_add_items(
        playlist_id=playlist["id"],
        items=normalize_ids(track_ids)[:100]
    )
    return playlist


def explain_track_features(track, emotion=None):
    """
    Return a simplified dictionary of key track info.
    """
    return {
        "name": track.get("name"),
        "artists": ", ".join([a["name"] for a in track.get("artists", [])]),
        "id": track.get("id"),
        "uri": track.get("uri"),
        "popularity": track.get("popularity"),
        "preview_url": track.get("preview_url"),
        "related_emotion": emotion
    }