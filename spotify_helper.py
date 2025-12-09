# spotify_helper.py

import os
import pathlib
from dotenv import load_dotenv
load_dotenv(override=True)
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import numpy as np
import time

# define the Spotify API scopes needed for the app
SCOPES = (
    "user-top-read "
    "user-read-recently-played "
    "user-read-private "
    "user-read-email "
    "user-library-read "
    "playlist-read-private "
    "playlist-modify-public "
    "playlist-modify-private"
)

# map music genres to moods
GENRE_TO_MOOD = {
    "pop": "happy", "dance": "happy", "edm": "happy",
    "rock": "angry", "metal": "angry", "punk": "angry",
    "jazz": "relaxed", "blues": "relaxed", "classical": "relaxed",
    "ambient": "relaxed", "folk": "happy", "rap": "angry",
    "hip hop": "anxious", "r&b": "relaxed", "country": "happy",
    "sad": "sad", "melancholy": "sad", "reggae": "relaxed", 
    "alternative rock": "happy", "grunge": "angry", "lo-fi": "relaxed",
    "latin": "happy", "soul": "relaxed"

}

# function to get an authenticated Spotify client
def get_spotify_client(cache_path=".cache-moodify"):
    # import Streamlit inside function to access session_state
    import streamlit as st
    # get Spotify client ID from environment
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    # get Spotify client secret from environment
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    # get redirect URI from environment or use default
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback")

    # resolve cache path to absolute path
    cache_path = str(pathlib.Path(cache_path).resolve())
    # create OAuth manager
    auth_manager = SpotifyOAuth(client_id, client_secret, redirect_uri, scope=SCOPES, cache_path=cache_path, show_dialog=True)

    # get token info from session state
    token_info = st.session_state.get("sp_token_info")
    # if no token info, get a new access token
    if not token_info:
        token_info = auth_manager.get_access_token(as_dict=True)
        st.session_state.sp_token_info = token_info
    # if token expired, refresh it
    elif auth_manager.is_token_expired(token_info):
        token_info = auth_manager.refresh_access_token(token_info["refresh_token"])
        st.session_state.sp_token_info = token_info

    # return authenticated Spotify client
    return spotipy.Spotify(auth_manager=auth_manager)

# wrapper for Spotify API calls with retries and error handling
def safe_spotify_call(sp, func, *args, max_retries=2, backoff=0.3, **kwargs):
    # loop for retry attempts
    for attempt in range(max_retries + 1):
        try:
            # attempt API call
            return func(*args, **kwargs)
        except spotipy.exceptions.SpotifyException as e:
            # get HTTP status code
            status = getattr(e, "http_status", None)
            # handle 401/403 by refreshing token
            if status in (401, 403):
                try:
                    auth = getattr(sp, "auth_manager", None)
                    if auth:
                        token_info = auth.get_cached_token()
                        if token_info:
                            auth.refresh_access_token(token_info['refresh_token'])
                except Exception:
                    pass
                # wait before retrying
                time.sleep(backoff * (attempt + 1))
                continue
            else:
                # raise for other errors
                raise
        except Exception:
            # wait before retrying for other exceptions
            time.sleep(backoff * (attempt + 1))
            continue
    # raise if all retries fail
    raise RuntimeError("Spotify API call failed after retries.")

# fetch candidate tracks from user's top, recent, and saved tracks
def get_user_candidate_tracks(sp, top_limit=50, recent_limit=50, saved_limit=50):
    # initialize empty candidates list and seen set
    candidates, seen = [], set()
    # helper to add track if not already seen or local
    def add(t):
        tid = t.get("id")
        if tid and tid not in seen and not t.get("is_local", False):
            candidates.append(t)
            seen.add(tid)

    # iterate over top, recent, and saved track functions and limits
    for items_func, limit in [(sp.current_user_top_tracks, top_limit),
                              (sp.current_user_recently_played, recent_limit),
                              (sp.current_user_saved_tracks, saved_limit)]:
        try:
            # get tracks safely
            items = safe_spotify_call(sp, items_func, limit=limit).get("items", [])
            for it in items:
                # extract track from item if present
                t = it.get("track") if "track" in it else it
                if t: add(t)
        except Exception:
            continue

    # return candidate tracks and empty diagnostics dict
    return candidates, {}

# fetch genres for a given track
def get_track_genres(sp, track):
    # initialize set for genres
    genres = set()
    # iterate over track artists
    for artist in track.get("artists", []):
        artist_id = artist.get("id")
        if not artist_id: continue
        try:
            # get artist info safely
            artist_info = safe_spotify_call(sp, sp.artist, artist_id)
            # add each genre in lowercase
            for g in artist_info.get("genres", []):
                genres.add(g.lower())
        except Exception:
            continue
    # return genres as list
    return list(genres)

# score and sample tracks based on genre matching and popularity
def score_and_sample_tracks_by_genre_and_popularity(tracks, target_emotion, k=10, seed=None):
    # return empty list if no tracks
    if not tracks: return []
    # set random seed if provided
    if seed: np.random.seed(seed)
    # initialize scores list
    scores = []
    # iterate over tracks
    for tr in tracks:
        # get mapped genres for track
        genres = tr.get("mapped_genres", [])
        # calculate match score
        match_score = sum(1 for g in genres if GENRE_TO_MOOD.get(g, "") == target_emotion) / max(len(genres),1)
        # get normalized popularity
        popularity = tr.get("popularity", 0) / 100.0
        # combine match score and popularity
        scores.append(0.7*match_score + 0.3*popularity)
    # calculate probabilities for sampling
    probs = np.array(scores) / np.sum(scores) if np.sum(scores) > 0 else np.ones(len(tracks))/len(tracks)
    # sample indices
    chosen = np.random.choice(len(tracks), size=min(k,len(tracks)), replace=False, p=probs)
    # return sampled tracks
    return [tracks[i] for i in chosen]

# create playlist and add tracks to Spotify
def create_playlist_and_add_tracks(sp, user_id, name, track_uris, description=""):
    # initialize list for prepared track URIs
    prepared = []
    # iterate over track URIs
    for t in track_uris:
        if isinstance(t,str):
            # add URI directly if already full URI
            if t.startswith("spotify:track:"): prepared.append(t)
            # format short ID
            elif len(t)==22: prepared.append(f"spotify:track:{t}")
            # extract ID from URL
            elif "open.spotify.com/track/" in t:
                tid = t.split("track/")[1].split("?")[0]
                prepared.append(f"spotify:track:{tid}")
    # create playlist safely
    pl = safe_spotify_call(sp, sp.user_playlist_create, user_id, name, public=False, description=description)
    # add tracks in batches of 100
    for i in range(0,len(prepared),100):
        safe_spotify_call(sp, sp.playlist_add_items, pl["id"], prepared[i:i+100])
    # return playlist object
    return pl

# format track features for display
def explain_track_features(track_obj, emotion=None):
    return {
        # track name
        "name": track_obj.get("name"),
        # track artists as comma-separated string
        "artists": ", ".join([a.get("name") for a in track_obj.get("artists", [])]) if track_obj.get("artists") else "",
        # track ID
        "id": track_obj.get("id"),
        # track URI
        "uri": track_obj.get("uri"),
        # track preview URL
        "preview_url": track_obj.get("preview_url"),
        # track popularity
        "popularity": track_obj.get("popularity"),
        # related emotion
        "related_emotion": emotion
    }
