# moodify.py

import streamlit as st
from spotify_helper import (
    get_spotify_client,
    get_user_top_and_recent_track_objects,
    fetch_audio_features_map,
    build_target_features_from_emotion,
    score_and_sample_tracks,
    create_playlist_and_add_tracks,
    explain_track_features
)
from emotion import EmotionDetector
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Moodify", layout="centered", initial_sidebar_state="expanded")
st.title("Moodify 🎧 — playlists that match or change your mood")

# sidebar: Spotify login + settings
st.sidebar.header("Spotify Connection")
if "sp" not in st.session_state:
    st.session_state.sp = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if st.session_state.sp is None:
    st.sidebar.write("Connect your Spotify account to get started.")
    if st.sidebar.button("Connect to Spotify"):
        try:
            sp = get_spotify_client()
            user = sp.current_user()
            st.session_state.sp = sp
            st.session_state.user_id = user["id"]
            st.success("Connected to Spotify as " + user.get("display_name", user.get("id", "unknown")))
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Spotify connect failed: {e}")
            raise
    st.stop()
else:
    st.sidebar.success("Spotify connected")

# app options
st.sidebar.markdown("---")
st.sidebar.header("Generation settings")
use_time_range = st.sidebar.selectbox("Use top tracks timeframe (seed pool)", ["medium_term", "short_term", "long_term"], index=0)
candidate_limit = st.sidebar.slider("How many candidate tracks to consider (top+recent combined)", 20, 100, 50, 10)
random_seed = st.sidebar.number_input("Optional random seed (empty=use randomness)", value=0, min_value=0, step=0)
if random_seed == 0:
    rand_seed = None
else:
    rand_seed = int(random_seed)

# main UI: mood input + mode
st.markdown("### Describe how you feel or how you want to feel")
prompt = st.text_area("Tell Moodify in natural language (ex. \"I'm nervous and need motivation to study\", \"cheer me up\")", height=120)

st.markdown("### Choose behavior")
behavior = st.radio("Playlist behavior:",
                    ("Match my mood — keep this vibe", "Change my mood — shift me toward a new vibe"))

# buttons: generate / refresh / create playlist
col1, col2, col3 = st.columns([1,1,1])
with col1:
    generate_clicked = st.button("Generate playlist")
with col2:
    refresh_clicked = st.button("Refresh playlist")
with col3:
    create_clicked = st.button("Create Spotify playlist (save)")

# internal session state for results & selected tracks
if "candidates" not in st.session_state:
    st.session_state.candidates = None  # list of track objects used as candidate pool
if "features_map" not in st.session_state:
    st.session_state.features_map = None  # map track_id -> audio features
if "current_playlist" not in st.session_state:
    st.session_state.current_playlist = None  # list of sampled track objects
if "last_emotion" not in st.session_state:
    st.session_state.last_emotion = None
if "last_behavior" not in st.session_state:
    st.session_state.last_behavior = None
if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = None

# helper to run generation pipeline
def run_generation(sp, prompt, behavior, time_range, limit, seed=None):
    """
    Runs the end-to-end generation:
      - detect emotion
      - collect user history (top + recent)
      - fetch audio features
      - compute target features (match vs change)
      - score candidates and sample 10 tracks
    Returns: (emotion_label, sampled_track_objects, features_map)
    """
    # detect emotion
    detector = EmotionDetector()
    pred = detector.predict(prompt)
    emotion = pred["top"]

    # get candidate tracks from user top + recent
    candidates = get_user_top_and_recent_track_objects(sp, top_limit=limit, time_range=time_range)

    # if no candidates, raise so UI can report
    if not candidates:
        return emotion, [], {}

    # fetch audio features map for candidate ids (id->features)
    track_ids = [t["id"] for t in candidates if t.get("id")]
    features_map = fetch_audio_features_map(sp, track_ids)

    # build target features from emotion + behavior
    target = build_target_features_from_emotion(emotion, behavior="match" if "Match" in behavior else "change")

    # score & sample 10 tracks
    sampled_indices = score_and_sample_tracks(list(features_map.values()), k=10, target=target, seed=seed)
    sampled_tracks = []
    # map back indices into track objects: features_map values aren't ordered by candidates
    # build list aligned with features_map order:
    ordered_features = [features_map[tid] for tid in track_ids if tid in features_map]
    # sometimes features_map misses items... ensure indices valid
    for idx in sampled_indices:
        if 0 <= idx < len(ordered_features):
            fid = ordered_features[idx]["id"]
            # find matching track object in candidates
            t = next((c for c in candidates if c.get("id") == fid), None)
            if t:
                sampled_tracks.append(t)

    return emotion, sampled_tracks, features_map

# generate or refresh logic
if generate_clicked or (refresh_clicked and st.session_state.current_playlist is not None):
    # use provided random seed or None
    seed_for_sampling = rand_seed
    try:
        emotion, sampled_tracks, features_map = run_generation(
            st.session_state.sp, prompt, behavior, use_time_range, candidate_limit, seed_for_sampling
        )
    except Exception as e:
        st.error(f"Generation failed: {e}")
        st.stop()

    if not sampled_tracks:
        st.info("No candidate tracks were available from your account. Try listening to Spotify a bit, or allow more tracks in settings.")
        st.stop()

    # store in session_state for UI & create action
    st.session_state.current_playlist = sampled_tracks
    st.session_state.features_map = features_map
    st.session_state.last_emotion = emotion
    st.session_state.last_behavior = behavior
    st.session_state.last_prompt = prompt

# display current playlist if exists
if st.session_state.current_playlist:
    st.markdown("## Generated Playlist (10 tracks)")
    st.markdown(f"**Detected emotion:** {st.session_state.last_emotion} • **Behavior:** {st.session_state.last_behavior}")
    for i, tr in enumerate(st.session_state.current_playlist, start=1):
        info = explain_track_features(tr, st.session_state.last_emotion)
        st.write(f"**{i}. {info['name']}** — {info['artists']}")
        if info.get("preview_url"):
            st.audio(info["preview_url"])
        # show condensed audio-feature explanation if available
        tf = st.session_state.features_map.get(tr["id"])
        if tf:
            st.markdown(f"- valence: {tf['valence']:.2f} • energy: {tf['energy']:.2f} • tempo: {tf['tempo']:.0f} • danceability: {tf['danceability']:.2f}")
        st.markdown("---")

    # create playlist saving
    if create_clicked:
        try:
            uris = [t["uri"] for t in st.session_state.current_playlist if t.get("uri")]
            if not uris:
                st.error("No URIs available to create a playlist.")
            else:
                playlist_name = f"Moodify: {st.session_state.last_emotion} ({'Match' if 'Match' in st.session_state.last_behavior else 'Change'})"
                description = f"Generated from prompt: {st.session_state.last_prompt}"
                pl = create_playlist_and_add_tracks(st.session_state.sp, st.session_state.user_id, playlist_name, uris, description=description)
                st.success("Playlist created!")
                st.markdown(f"[Open Playlist]({pl['external_urls']['spotify']})")
        except Exception as e:
            st.error(f"Failed to create playlist: {e}")

else:
    st.info("No playlist generated yet. Describe your mood above and click 'Generate playlist'.")

# small footer
st.markdown("---")
st.caption("Moodify uses your Spotify listening history (top + recently played) and a lightweight emotion classifier to produce playlists you can save to your account.")