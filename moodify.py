# moodify.py

import streamlit as st
from emotion import EmotionDetector
from spotify_helper import (
    get_spotify_client,
    get_user_candidate_tracks,
    score_and_sample_tracks_by_genre_and_popularity,
    create_playlist_and_add_tracks,
    get_track_genres,
    explain_track_features
)

# Set up the page
st.set_page_config(page_title="Moodify", layout="centered")
st.title("Moodify - Emotion-aware playlist generation!")

# Spotify connection
st.sidebar.header("Spotify Connection")
if "sp" not in st.session_state: st.session_state.sp = None
if "user_id" not in st.session_state: st.session_state.user_id = None

if st.session_state.sp is None:
    st.sidebar.write("Connect your Spotify account to get started...")
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
    st.stop()
else:
    st.sidebar.success("Spotify connected")

# Generation settings
st.sidebar.header("Generation settings")
random_seed = st.sidebar.number_input("Optional random seed (0=random)", value=0, min_value=0)
rand_seed = int(random_seed) if random_seed != 0 else None

# Mood input
st.markdown("### Describe your current mood")
prompt = st.text_area("Tell Moodify your current mood in simple words:", height=120)

# Playlist behavior
st.markdown("### Playlist behavior")
behavior = st.radio("Choose behavior:", ("Match Mood", "Change Mood"))

# Action buttons
col1, col2 = st.columns([1,1])
with col1: generate_clicked = st.button("Generate")
with col2: create_clicked = st.button("Save to Spotify")

# Emotion detector
detector = EmotionDetector()

def choose_target_mood(current):
    if current in ["sad", "angry", "anxious"]:
        return "happy"
    if current == "happy":
        return "relaxed"
    if current == "relaxed":
        return "happy"
    alternatives = ["happy", "sad", "angry", "anxious", "relaxed"]
    return [m for m in alternatives if m != current][0]

def run_generation(sp, prompt, behavior, limit=50, seed=None):
    current_mood = detector.predict(prompt)["top"]

    candidates, _ = get_user_candidate_tracks(sp, top_limit=limit, recent_limit=limit, saved_limit=limit)
    if not candidates:
        return current_mood, []

    for tr in candidates:
        tr["mapped_genres"] = get_track_genres(sp, tr)

    target_mood = choose_target_mood(current_mood) if behavior == "Change Mood" else current_mood
    sampled_tracks = score_and_sample_tracks_by_genre_and_popularity(candidates, target_mood, k=10, seed=seed)
    return current_mood, sampled_tracks

if generate_clicked:
    try:
        emotion, sampled_tracks = run_generation(st.session_state.sp, prompt, behavior, seed=rand_seed)
    except Exception as e:
        st.error(f"Generation failed: {e}")
        st.stop()

    if not sampled_tracks:
        st.info("No candidate tracks available. Listen to more tracks or try again later.")
        st.stop()

    st.session_state.current_playlist = sampled_tracks
    st.session_state.last_emotion = emotion
    st.session_state.last_behavior = behavior
    st.session_state.last_prompt = prompt

# Display playlist
if "current_playlist" in st.session_state and st.session_state.current_playlist:
    st.markdown("## Moodify-Generated Playlist")
    st.markdown(f"**Detected Mood:** {st.session_state.last_emotion} | **Behavior:** {st.session_state.last_behavior}")
    for i, tr in enumerate(st.session_state.current_playlist, start=1):
        info = explain_track_features(tr, st.session_state.last_emotion)
        st.write(f"**{i}. {info['name']}** — {info['artists']}")
        if info.get("preview_url"): st.audio(info["preview_url"])
        st.markdown("---")

    if create_clicked:
        uris = [t["uri"] for t in st.session_state.current_playlist if t.get("uri")]
        if uris:
            playlist_name = f"Moodify: {st.session_state.last_emotion} ({'Match' if behavior=='Match Mood' else 'Change'})"
            description = f"Generated from prompt: {prompt}"
            try:
                pl = create_playlist_and_add_tracks(st.session_state.sp, st.session_state.user_id, playlist_name, uris, description=description)
                st.success("Playlist created!")
                ext = pl.get("external_urls", {}).get("spotify")
                if ext: st.markdown(f"[Open Playlist]({ext})")
            except Exception as e:
                st.error(f"Failed to create playlist: {e}")
else:
    st.info("Click 'Generate' to create a playlist.")
