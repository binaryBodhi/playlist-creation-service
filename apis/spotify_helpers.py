from .utilities import _api_request
import urllib.parse
from typing import Dict, List, Optional, Tuple
from .constants import API_BASE, ADD_BATCH_LIMIT

def _current_user_id(token: str) -> str:
    me = _api_request("GET", "/me", token)
    return me["id"]


def _iter_pages(token: str, path: str, params: Optional[dict] = None):
    params = dict(params or {})
    params.setdefault("limit", 50)
    url = f"{API_BASE}{path}"
    while True:
        data = _api_request("GET", url, token, params=params)
        items = data.get("items", [])
        for it in items:
            yield it
        if data.get("next"):
            url = data["next"]
            params = None  # next already contains query
        else:
            break


def _parse_playlist_id(url_or_id: str) -> str:

    # Accept raw ID or full URL
    if "open.spotify.com/playlist/" in url_or_id:
        parts = urllib.parse.urlparse(url_or_id)
        segs = parts.path.rstrip("/").split("/")
        return segs[-1]
    return url_or_id


def _is_track_item(item: dict) -> bool:
    # Guard against episodes, locals, and null track
    if not item or item.get("is_local"):
        return False
    track = item.get("track")
    if not track:
        return False
    return track.get("type") == "track"


def _track_uri_and_year(item: dict) -> Optional[Tuple[str, Optional[str]]]:
    track = item.get("track")
    if not track:
        return None
    uri = track.get("uri")
    album = track.get("album") or {}
    release_date = album.get("release_date")
    if not uri or not release_date:
        return None
    # release_date can be YYYY, YYYY-MM, or YYYY-MM-DD; take the first 4 chars.
    year = release_date[:4] if len(release_date) >= 4 else None
    return uri, year


def _find_user_playlist_by_name(token: str, user_id: str, name_exact: str) -> Optional[str]:
    # List current user's playlists and look for exact name match
    for it in _iter_pages(token, "/me/playlists", params={"limit": 50}):
        if it.get("name") == name_exact and it.get("owner", {}).get("id") == user_id:
            return it.get("id")
    return None


def _get_playlist_track_uris(token: str, playlist_id: str) -> List[str]:
    uris = []
    for it in _iter_pages(
        token,
        f"/playlists/{playlist_id}/tracks",
        params={"fields": "items(is_local,track(uri,type)),next,items.track.uri", "limit": 100, "additional_types": "track"},
    ):
        if _is_track_item(it):
            t = it.get("track") or {}
            u = t.get("uri")
            if u:
                uris.append(u)
    return uris


def _create_playlist(token: str, user_id: str, name: str, description: str, public: bool = False) -> str:
    body = {"name": name, "description": description, "public": public}
    pl = _api_request("POST", f"/users/{user_id}/playlists", token, json_body=body)
    return pl["id"]


def _get_playlist(token: str, playlist_id: str) -> dict:
    return _api_request("GET", f"/playlists/{playlist_id}", token, params={"market": "from_token"})


def _add_items_in_batches(token: str, playlist_id: str, uris: List[str]) -> None:
    for i in range(0, len(uris), ADD_BATCH_LIMIT):
        chunk = uris[i : i + ADD_BATCH_LIMIT]
        _api_request("POST", f"/playlists/{playlist_id}/tracks", token, json_body={"uris": chunk})


def _playlist_is_owned_by_user(pl: dict, user_id: str) -> bool:
    return (pl.get("owner") or {}).get("id") == user_id

def _playlist_has_tag(pl: dict, tag: str) -> bool:
    desc = pl.get("description") or ""
    return tag in desc

def _unfollow_playlist(token: str, playlist_id: str) -> None:
    # DELETE /v1/playlists/{playlist_id}/followers
    _api_request("DELETE", f"/playlists/{playlist_id}/followers", token)

def _iter_my_playlists(token: str):
    # Iterate all of *your* playlists
    yield from _iter_pages(token, "/me/playlists", params={"limit": 50})
