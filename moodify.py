# moodify.py
import streamlit as st
from emotion import EmotionDetector
from spotify_helper import (
    get_spotify_client,
    recommend_tracks,
    create_playlist_and_add_tracks,
    explain_track_features
)
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Moodify", layout="centered")
st.title("Moodify")

if "spotify" not in st.session_state:
    st.session_state.spotify = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_country" not in st.session_state:
    st.session_state.user_country = None

if st.session_state.spotify is None:
    st.markdown("Connect your Spotify account first to continue.")

    if st.button("Connect to Spotify"):
        try:
            sp = get_spotify_client()
            user = sp.current_user()

            st.session_state.spotify = sp
            st.session_state.user_id = user["id"]
            # store user country (may not exist for some accounts)
            st.session_state.user_country = user.get("country")
            st.session_state.logged_in = True

            st.rerun()
        except Exception as e:
            st.error(f"Failed to connect to Spotify: {e}")

    st.stop()

st.success("Spotify connected!")

mode = st.radio("Playlist behavior", ["Match my mood", "Change my mood (cheer me up / calm me down)"])

text = st.text_area(
    "Describe your mood / request",
    value="I'm feeling nervous but need motivation to study",
    height=120
)

if "rec_results" not in st.session_state:
    st.session_state.rec_results = None

if "results" not in st.session_state:
    st.session_state.results = None
if "emotion_label" not in st.session_state:
    st.session_state.emotion_label = None

if st.button("Generate playlist"):
    if not text.strip():
        st.warning("Enter text describing your current or desired mood.")
        st.stop()

    # detect emotion
    with st.spinner("Detecting emotion..."):
        detector = EmotionDetector()
        res = detector.predict(text)

    st.session_state.emotion_label = res["top"]

    st.subheader("Detected emotion")
    st.write(f"Top: **{res['top']}** (confidence {res['top_score']:.2f})")
    st.json(res["scores"])

    sp = st.session_state.spotify

    # detect market/country if available; recommend_tracks will work w/out it
    market = st.session_state.get("user_country")

    detected = st.session_state.emotion_label

    if mode == "Change my mood (cheer me up / calm me down)":
        from spotify_helper import MOOD_CHANGE_MAP
        target = MOOD_CHANGE_MAP.get(detected, detected)   # fallback to self
    else:
        target = detected  # match mood mode

    tracks = recommend_tracks(
        sp,
        market=market,
        change_mood=target,
    )

    st.session_state.results = tracks

# show results
results = st.session_state.results
if results and results.get("tracks"):
    st.subheader("Top recommendations + explanations")

    for t in results["tracks"][:10]:
        info = explain_track_features(t, st.session_state.emotion_label)
        st.write(f"{info['name']} - {info['artists']}")
        st.write(f"Preview: {info['preview_url']}")
        st.json(info)
        st.markdown("---")

    if st.button("Create Spotify Playlist"):
        # collect URIs safely
        uris = [t.get("uri") for t in results["tracks"] if t.get("uri")]

        if not uris:
            st.error("No valid or playable tracks were returned. Try a different mood.")
            st.stop()

        playlist_name = f"Moodify: {st.session_state.emotion_label or 'playlist'}"
        description = f"Generated from: {text}"

        try:
            playlist = create_playlist_and_add_tracks(
                st.session_state.spotify,
                st.session_state.user_id,
                playlist_name,
                uris,
                description=description
            )
            st.success("Playlist created!")
            st.markdown(f"[Open Playlist]({playlist['external_urls']['spotify']})")
        except Exception as e:
            st.error(f"Failed to create playlist: {e}")
else:
    # helpful hint when there are no results yet
    if st.session_state.results is not None:
        st.info("No recommendations were returned. Try toggling mode, simplifying the request, or using a different input text.")
