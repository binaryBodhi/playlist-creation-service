import requests
import time
import string
import random
import os
import json
import base64
import hashlib

from typing import Dict, List, Optional, Tuple
from .constants import API_BASE, TOKEN_PATH


def _api_request(
    method: str,
    path: str,
    token: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
    max_retries: int = 5,
):
    """
    Wrapper for Spotify Web API calls with simple 429 retry handling.
    """
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    for attempt in range(max_retries):
        resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=30)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "1"))
            time.sleep(retry_after)
            continue
        if 200 <= resp.status_code < 300:
            if resp.text:
                return resp.json()
            return None
        # Some read endpoints return 204 (no content) on success; treat as ok
        if resp.status_code == 204:
            return None
        # Otherwise raise with context
        try:
            detail = resp.json()
        except Exception:
            detail = {"error": resp.text}
        raise RuntimeError(f"Spotify API error {resp.status_code} on {method} {url}: {detail}")
    raise RuntimeError("Exceeded retry attempts due to rate limiting.")


def _now() -> int:
    return int(time.time())


def _code_challenge_from_verifier(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _random_string(n: int = 64) -> str:
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(random.choice(alphabet) for _ in range(n))


def _token_expired(tok: dict, leeway: int = 30) -> bool:
    # We store obtained_at and expires_in; consider expired if within `leeway` seconds.
    if not tok:
        return True
    expires_at = tok.get("obtained_at", 0) + tok.get("expires_in", 0)
    return _now() >= (expires_at - leeway)


def _load_token() -> Optional[dict]:

    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            tok = json.load(f)
        return tok
    except Exception:
        return None
    

def _save_token(tok: dict) -> None:
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(tok, f, indent=2)