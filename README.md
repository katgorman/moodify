# Moodify: Emotion-Aware Spotify Playlist Generator

Moodify is a Streamlit web app that generates Spotify playlists based on
your current mood, detected from natural language using a large language
model. It can either match your mood or intentionally shift it, then
builds a personalized playlist using your current mood listening habits.

------------------------------------------------------------------------

## Features

-   AI-powered emotion detection from text prompts\
-   Spotify integration using your real top, recent, and saved tracks\
-   Mood-based track scoring using genres and popularity\
-   Match or change your mood with one click\
-   One-click playlist creation directly in Spotify\
-   Optional random seed for reproducibility

------------------------------------------------------------------------

## Project Structure

    moodify/
    │
    ├── moodify.py          # Main Streamlit app
    ├── spotify_helper.py  # Spotify API utilities and playlist logic
    ├── emotion.py         # LLM-based emotion detection
    ├── requirements.txt   # Python dependencies
    └── .env               # Spotify API credentials (not committed)

------------------------------------------------------------------------

## How It Works

1.  The user enters a text description of their current mood.
2.  An LLM running through Ollama classifies the mood.
3.  Moodify gathers candidate tracks from:
    -   Top tracks
    -   Recently played tracks
    -   Saved library
4.  Each track is scored based on:
    -   How well its genres match the target mood
    -   Track popularity
5.  Tracks are probabilistically sampled and displayed with previews.
6.  The playlist can be saved directly to the user's Spotify account.

------------------------------------------------------------------------

## Requirements

-   Python 3.9+
-   Spotify Developer Account
-   Ollama installed locally

Python dependencies are listed in `requirements.txt`:

    streamlit
    transformers
    torch
    spotipy
    numpy
    pandas
    python-dotenv
    ollama

------------------------------------------------------------------------

## Environment Setup

Create a `.env` file in the project root with the following:

    SPOTIPY_CLIENT_ID=your_client_id
    SPOTIPY_CLIENT_SECRET=your_client_secret
    SPOTIPY_REDIRECT_URI=http://localhost:8888/callback

------------------------------------------------------------------------

## Running the App

From the project directory:

    pip install -r requirements.txt
    streamlit run moodify.py

Then open the local Streamlit URL in your browser and connect your
Spotify account.

------------------------------------------------------------------------

## File Descriptions

### moodify.py

The main Streamlit app. Handles: - Spotify authentication - Mood input -
Playlist generation - Track previews - Playlist creation

### spotify_helper.py

Contains all Spotify API logic: - Authentication and token refresh -
Safe API calls with retries - Pulling user track history - Genre
extraction - Mood-based scoring and sampling - Playlist creation

### emotion.py

Handles emotion classification using an Ollama LLM: - Prompts the model
with strict output rules - Returns one of: happy, sad, relaxed, anxious,
angry, neutral

------------------------------------------------------------------------

## Notes

-   This project depends on local LLM inference via Ollama.
-   Spotify API rate limits may affect large requests.
-   Genre-to-mood mapping is heuristic and can be customized.
-   Generated playlists are private by default.

------------------------------------------------------------------------

