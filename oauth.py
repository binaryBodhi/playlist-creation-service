from .utilities import (
    _token_expired,
    _load_token,
    _random_string,
    _code_challenge_from_verifier,
    _now,
    _save_token
)

from .httpServer import _run_temp_server_and_wait_for_code

from .constants import _get_spotify_client_id, ACCOUNTS_BASE, REDIRECT_URI, SCOPES


import requests
import urllib.parse

def _ensure_token() -> dict:
    tok = _load_token()
    if not tok or _token_expired(tok):
        if tok and "refresh_token" in tok:
            tok = _refresh_token(tok)
        else:
            tok = _authorize_with_pkce()
    return tok


def _authorize_with_pkce() -> dict:
    global SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_ID = _get_spotify_client_id()
    if not SPOTIFY_CLIENT_ID:
        raise RuntimeError("Missing SPOTIFY_CLIENT_ID. Export it in your environment.")

    verifier = _random_string(64)
    challenge = _code_challenge_from_verifier(verifier)
    state = _random_string(24)

    auth_params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "state": state,
        "show_dialog": "true",
    }
    auth_url = f"{ACCOUNTS_BASE}/authorize?{urllib.parse.urlencode(auth_params)}"

    code = _run_temp_server_and_wait_for_code(state, auth_url)

    token_data = {
        "client_id": SPOTIFY_CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }
    tok = requests.post(f"{ACCOUNTS_BASE}/api/token", data=token_data, timeout=30)
    if tok.status_code != 200:
        raise RuntimeError(f"Token exchange failed: {tok.status_code} {tok.text}")
    token_json = tok.json()
    token_json["obtained_at"] = _now()
    _save_token(token_json)
    return token_json


def _refresh_token(tok: dict) -> dict:
    if not tok or "refresh_token" not in tok:
        return _authorize_with_pkce()
    data = {
        "client_id": _get_spotify_client_id(),
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
    }
    r = requests.post(f"{ACCOUNTS_BASE}/api/token", data=data, timeout=30)
    if r.status_code != 200:
        # Fallback to full reauth
        return _authorize_with_pkce()
    new_tok = tok.copy()
    new_tok.update(r.json())
    new_tok["obtained_at"] = _now()
    # Keep the original refresh_token if a new one isn't returned
    if "refresh_token" not in new_tok:
        new_tok["refresh_token"] = tok.get("refresh_token")
    _save_token(new_tok)
    return new_tok