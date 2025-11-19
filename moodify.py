import streamlit as st
from emotion import EmotionDetector
from spotify_helper import get_spotify_client, recommend_tracks, create_playlist_and_add_tracks, explain_track_features
import os
from dotenv import load_dotenv

load_dotenv()  

st.set_page_config(page_title="Moodify", layout="centered")
st.title("Moodify")

if "spotify" not in st.session_state:
    st.session_state.spotify = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if st.session_state.spotify is None:
    st.markdown("Connect your Spotify account first to continue.")

    if st.button("Connect to Spotify"):
        try:
            sp = get_spotify_client()   # OAuth redirect happens here
            user = sp.current_user()

            # Save everything BEFORE rerunning
            st.session_state.spotify = sp
            st.session_state.user_id = user["id"]
            st.session_state.logged_in = True

            st.rerun()   # now the UI below will show
        except Exception as e:
            st.error(f"Failed to connect to Spotify: {e}")

    st.stop()

# show full UI once Spotify is connected
st.success("Spotify connected!")

mode = st.radio("Playlist behavior", ["Match my mood", "Change my mood (cheer me up / calm me down)"])

text = st.text_area(
    "Describe your mood / request",
    value="I'm feeling nervous but need motivation to study",
    height=120
)

if st.button("Generate playlist"):
    if not text.strip():
        st.warning("Please enter text describing your mood.")
        st.stop()

    with st.spinner("Detecting emotion..."):
        detector = EmotionDetector()
        res = detector.predict(text)

    st.subheader("Detected emotion")
    st.write(f"Top: **{res['top']}** (confidence {res['top_score']:.2f})")
    st.json(res["scores"])

    sp = st.session_state.spotify

    change_mood = (mode == "Change my mood (cheer me up / calm me down)")
    tracks = recommend_tracks(sp, res["top"], seed_tracks=None, change_mood=change_mood)

    st.subheader("Top recommendations with explanations")
    for t in tracks[:10]:
        st.write(f"### {t['name']} — {t['artists']}")
        st.write(f"Preview: {t['preview_url']}")
        explanation = explain_track_features(t, res['top'])
        st.write(explanation)
        st.markdown("---")

    # create playlist button
    if st.button("Create Spotify Playlist Now"):
        playlist_name = f"Moodify — {res['top']} mood"
        description = f"Generated from: \"{text}\""

        uris = [t["uri"] for t in tracks]

        playlist = create_playlist_and_add_tracks(
            sp,
            st.session_state.user_id,
            playlist_name,
            uris,
            public=False,
            description=description
        )

        st.success("Playlist created successfully!")
        st.markdown(f"[Open Playlist on Spotify]({playlist['external_urls']['spotify']})")
