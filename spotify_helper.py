# spotify_helper.py 
import spotipy
from spotipy.oauth2 import SpotifyOAuth

MOOD_CHANGE_MAP = {
    "happy":   "relaxed",    # too hyped... relax
    "sad":     "happy",      # cheer up
    "angry":   "relaxed",    # calm down
    "anxious": "relaxed",    # soothe
    "relaxed": "happy",      # energize
}


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
    Accepts a list of:
      - track dicts (with 'id' or 'uri')
      - track URIs: spotify:track:<id>
      - spotify track URLs: https://open.spotify.com/track/<id>
      - plain 22-char track IDs
    Returns list of cleaned strings (prefer URIs if available, otherwise IDs).
    """
    cleaned = []
    for s in seeds or []:
        if not s:
            continue
        # dict with id or uri
        if isinstance(s, dict):
            if s.get("uri"):
                cleaned.append(s["uri"])
            elif s.get("id"):
                cleaned.append(s["id"])
            continue
        if not isinstance(s, str):
            continue
        s = s.strip()
        # spotify URI
        if s.startswith("spotify:track:"):
            cleaned.append(s)
            continue
        # spotify web url
        if "open.spotify.com/track/" in s:
            try:
                _id = s.split("track/")[1].split("?")[0]
                cleaned.append(_id)
                continue
            except Exception:
                cleaned.append(s)
                continue
        # 22-char id
        if len(s) == 22 and all(c.isalnum() or c in "-_" for c in s):
            cleaned.append(s)
            continue
        # fallback: keep the string (Spotify endpoints accept URIs or IDs)
        cleaned.append(s)
    return cleaned


def recommend_tracks(
    sp,
    market=None,
    top_tracks=None,
    seed_tracks=None,
    change_mood=None,
    limit=20,
    fallback_genres=("pop", "indie", "rock"),
    debug=False,
):
    """
    Robust recommendation generator.

    Improvements over original:
    - no hardcoded US market (optional market detection)
    - seed normalization accepts URIs/IDs/objects
    - validate tracks more carefully (without depending on market)
    - multiple fallbacks including search
    - detailed logging (enable debug=True)
    """
    def log(*args):
        if debug:
            print("[recommend_tracks]", *args)

    def validate_track(track_id_or_uri):
        """
        Return the full track object if playable, else None.
        We call sp.track without passing market to avoid strict market filtering.
        """
        try:
            # extract id if a spotify: URI was provided
            if isinstance(track_id_or_uri, str) and track_id_or_uri.startswith("spotify:track:"):
                tid = track_id_or_uri.split("spotify:track:")[1]
            else:
                tid = track_id_or_uri
            t = sp.track(tid)
            if not t:
                log("validate_track: no track object for", tid)
                return None
            if t.get("is_playable") is False:
                log("validate_track: is_playable False for", tid)
                return None
            if t.get("restrictions", {}).get("reason") in ("market", "premium"):
                log("validate_track: restricted for", tid, "reason:", t.get("restrictions", {}).get("reason"))
                return None
            if not t.get("uri"):
                log("validate_track: no uri for", tid)
                return None
            return t
        except Exception as e:
            log("validate_track exception for", track_id_or_uri, e)
            return None

    def safe_recs(**kwargs):
        try:
            r = sp.recommendations(limit=limit, **{k: v for k, v in kwargs.items() if v is not None})
            if isinstance(r, dict):
                log("safe_recs called:", {k: (type(v).__name__ if k in ('seed_tracks','seed_genres') else v) for k,v in kwargs.items()}, "-> tracks:", len(r.get("tracks", [])))
            else:
                log("safe_recs returned non-dict:", type(r))
            return r
        except Exception as e:
            log("safe_recs exception:", e)
            return None

    # normalize incoming seeds (IDs/URIs/dicts)
    raw_seeds = normalize_ids(seed_tracks or top_tracks or [])
    log("raw_seeds:", raw_seeds)

    # validate seed tracks (and collect playable track objects)
    valid_seed_objs = []
    for s in raw_seeds:
        t = validate_track(s)
        if t:
            valid_seed_objs.append(t)
    valid_seeds = []
    # convert to acceptable seed format for recommendations: use track IDs (not URIs)
    for t in valid_seed_objs[:5]:
        if t.get("id"):
            valid_seeds.append(t["id"])
    log("valid_seeds (IDs):", valid_seeds)

    # prepare mood kwargs safely (only if change_mood matches EMOTION_FEATURES)
    mood_kwargs = {}
    if isinstance(change_mood, str) and change_mood in EMOTION_FEATURES:
        mood_kwargs = {k: v for k, v in EMOTION_FEATURES[change_mood].items() if v is not None}
    log("change_mood:", change_mood, "mood_kwargs:", mood_kwargs)

    # 1) try validated seed tracks (if any)
    if valid_seeds:
        log("Attempting recommendations with seed_tracks:", valid_seeds)
        result = safe_recs(seed_tracks=valid_seeds, **mood_kwargs)
        if result and result.get("tracks"):
            log("Got tracks from seed_tracks fallback:", len(result["tracks"]))
            return result
        log("No tracks returned with validated seed_tracks.")

    # 2) try fallback genres
    log("Attempting recommendations with seed_genres:", fallback_genres)
    result = safe_recs(seed_genres=list(fallback_genres), **mood_kwargs)
    if result and result.get("tracks"):
        log("Got tracks from fallback_genres:", len(result["tracks"]))
        return result
    log("No tracks returned from fallback_genres.")

    # 3) try focused 'pop' genre
    log("Attempting emergency seed_genres=['pop']")
    result = safe_recs(seed_genres=["pop"], **mood_kwargs)
    if result and result.get("tracks"):
        log("Got tracks from seed_genres=['pop']:", len(result["tracks"]))
        return result
    log("No tracks returned from seed_genres=['pop'].")

    # 4) search-based fallback: look up popular artists/tracks and return first playable
    log("Attempting search-based fallback.")
    search_queries = [
        "Taylor Swift", "The Beatles", "Ed Sheeran", "Billie Eilish", "Coldplay",
        "Adele", "Drake", "BTS", "The Weeknd", "Bruno Mars"
    ]
    for q in search_queries:
        try:
            s = sp.search(q, limit=8, type="track")
            tracks = s.get("tracks", {}).get("items", []) if isinstance(s, dict) else []
            log(f"search('{q}') found {len(tracks)} tracks")
            for t in tracks:
                playable = validate_track(t.get("id"))
                if playable:
                    log("Found playable search fallback:", playable.get("name"), "by", ", ".join(a["name"] for a in playable.get("artists", [])[:2]))
                    return {"tracks": [playable]}
        except Exception as e:
            log("search exception for", q, e)

    # 5) last-ditch known-good track ids (try a few popular ids)
    log("Attempting known-good track IDs fallback.")
    known_good_ids = [
        "3KkXRkHbMCARz0aVfEt68P",  # Sunflower (Post Malone & Swae Lee)
        "4aWmUDTfIPGksMNLV2rQP2",  # Believer (Imagine Dragons)
        "0e7ipj03S05BNilyu5bRzt",  # Hotline Bling snippet etc (examples)
    ]
    for kid in known_good_ids:
        try:
            t = validate_track(kid)
            if t:
                log("Returning known-good track id:", kid)
                return {"tracks": [t]}
        except Exception as e:
            log("known-good exception", kid, e)

    # 6) exhausted fallback options... return empty list
    log("All fallbacks exhausted — returning {'tracks': []}")
    return {"tracks": []}


def create_playlist_and_add_tracks(sp, user_id, name, track_ids, description=None):
    """
    Accepts a list of track URIs or IDs or track dicts and creates a playlist,
    adding up to 100 items per request chunk. Raises ValueError if no valid items.
    """
    # normalize incoming list to URIs or IDs
    items = normalize_ids(track_ids or [])
    # convert IDs to URIs where possible (Spotify API accepts either, but URIs are safe)
    prepared = []
    for it in items:
        if isinstance(it, str) and it.startswith("spotify:track:"):
            prepared.append(it)
        elif isinstance(it, str) and len(it) == 22:
            prepared.append(f"spotify:track:{it}")
        elif isinstance(it, str) and "open.spotify.com/track/" in it:
            try:
                tid = it.split("track/")[1].split("?")[0]
                prepared.append(f"spotify:track:{tid}")
            except Exception:
                prepared.append(it)
        elif isinstance(it, dict) and it.get("uri"):
            prepared.append(it["uri"])
        else:
            # fallback: keep as-is hoping it's an ID or uri
            prepared.append(it)

    # filter falsy
    prepared = [p for p in prepared if p]
    if not prepared:
        raise ValueError("No valid track URIs/IDs to add to playlist.")

    # create playlist
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=False,
        description=description or ""
    )

    # add in chunks of 100
    for i in range(0, len(prepared), 100):
        chunk = prepared[i:i+100]
        sp.playlist_add_items(playlist_id=playlist["id"], items=chunk)

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
