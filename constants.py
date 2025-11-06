import os



def _get_spotify_client_id() -> str:
    return (os.getenv("SPOTIFY_CLIENT_ID", "")).strip()



# SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5555/callback")
TOKEN_PATH = os.path.expanduser("~/.spotify_year_splitter_token.json")

SCOPES = [
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-private",
    # Note: not requesting playlist-modify-public since we default to private output.
    # Add "playlist-modify-public" if you want to create public playlists.
]

ACCOUNTS_BASE = "https://accounts.spotify.com"
API_BASE = "https://api.spotify.com/v1"
ADD_BATCH_LIMIT = 100