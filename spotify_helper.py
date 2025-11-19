# spotify_helper.py
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
    """Convert a list of track dicts or strings into a list of track IDs."""
    cleaned = []
    for s in seeds:
        if isinstance(s, dict) and "id" in s:
            cleaned.append(s["id"])
        elif isinstance(s, str):
            cleaned.append(s)
    return cleaned


def recommend_tracks(
    sp,
    market="US",
    top_tracks=None,
    seed_tracks=None,
    change_mood=None,
    limit=20,
    fallback_genres=("pop", "indie", "rock"),
):
    """
    A robust Spotify recommendation generator w/:
    - market validation
    - seed validation + playability checks
    - safe mood parameter filtering
    - guaranteed fallback seeds
    - protection against 404/invalid parameter errors - this is giving me SHIT
    """
    # HELPER: check track exists + is playable 
    def validate_track(track_id):
        try:
            t = sp.track(track_id, market=market)
            if not t:
                return False
            if t.get("is_playable") is False:
                return False
            # Spotify sometimes omits 'is_playable'; fallback check:
            if t.get("restrictions", {}).get("reason") in ("market", "premium"):
                return False
            return True
        except Exception:
            return False

    # Step 1: normalize IDs
    raw_seeds = normalize_ids(seed_tracks or top_tracks or [])

    # Step 2: validate seeds against API & market
    valid_seeds = [tid for tid in raw_seeds if validate_track(tid)]

    # keep max 5
    valid_seeds = valid_seeds[:5]

    # Step 3: clean mood params
    mood_kwargs = (
        EMOTION_FEATURES.get(change_mood, {}).copy()
        if change_mood in EMOTION_FEATURES
        else {}
    )
    mood_kwargs = {k: v for k, v in mood_kwargs.items() if v is not None}


    # HELPER safe wrapper around sp.recommendations
    def safe_recs(**kwargs):
        """
        Spotify sometimes returns 404 for no reason.
        This wrapper tries the request safely.
        """
        try:
            return sp.recommendations(limit=limit, market=market, **kwargs)
        except Exception as e:
            print("Spotify recommendation error:", e)
            return None

    # Step 4: Use validated seed tracks first
    if valid_seeds:
        result = safe_recs(seed_tracks=valid_seeds, **mood_kwargs)
        if result and result.get("tracks"):
            return result

    # Step 5: fallback to genres 
    result = safe_recs(seed_genres=list(fallback_genres), **mood_kwargs)
    if result and result.get("tracks"):
        return result

    # Step 6: last-resort fallback
    # use Spotify's required minimum: one seed of any kind
    print("Emergency fallback: using seed_genres=['pop']")
    return safe_recs(seed_genres=["pop"]) or {"tracks": []}


def create_playlist_and_add_tracks(sp, user_id, name, track_ids, description=None):
    track_ids = normalize_ids(track_ids or [])

    if not track_ids:
        raise ValueError("No valid tracks were returned, cannot add to playlist.")

    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=False,   
        description=description or ""
    )

    sp.playlist_add_items(
        playlist_id=playlist["id"],
        items=track_ids[:100]
    )

    return playlist


def explain_track_features(track, emotion=None):
    """Return a simplified dictionary of key track info."""
    return {
        "name": track.get("name"),
        "artists": ", ".join([a["name"] for a in track.get("artists", [])]),
        "id": track.get("id"),
        "uri": track.get("uri"),
        "popularity": track.get("popularity"),
        "preview_url": track.get("preview_url"),
        "related_emotion": emotion
    }