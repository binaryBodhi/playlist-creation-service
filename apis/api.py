import argparse
import time

from .oauth import _ensure_token
from typing import Dict, List, Optional
from .constants import DESCRIPTION_TAG

from .spotify_helpers import (
    _current_user_id, 
    _parse_playlist_id, 
    _get_playlist,
    _iter_pages,
    _track_uri_and_year,
    _find_user_playlist_by_name,
    _create_playlist,
    _get_playlist_track_uris,
    _add_items_in_batches,
    _iter_my_playlists,
    _playlist_is_owned_by_user,
    _playlist_has_tag,
    _unfollow_playlist
)

def delete_year_playlists(
    source_name: str,
    year: Optional[str] = None,
    require_tag: bool = True,
    dry_run: bool = True,
    force: bool = False,
) -> dict:
    """
    Find year-playlists created from `source_name` and unfollow (delete) them.
    Returns a summary dict.

    - If year is provided, only targets that year.
    - If require_tag is True, only targets playlists whose description contains DESCRIPTION_TAG.
    - If dry_run is True, only lists matching playlists (does not unfollow).
    """
    tok = _ensure_token()
    access_token = tok["access_token"]
    user_id = _current_user_id(access_token)

    if year:
        name_targets = {f"From {source_name}: {year}"}
        name_prefix = None
    else:
        name_targets = None
        name_prefix = f"From {source_name}: "

    found = []
    skipped_not_owner = []
    skipped_no_tag = []

    for pl in _iter_my_playlists(access_token):
        name = pl.get("name") or ""
        if name_targets is not None:
            if name not in name_targets:
                continue
        else:
            if not name.startswith(name_prefix):
                continue

        # Only consider playlists you own
        if not _playlist_is_owned_by_user(pl, user_id):
            skipped_not_owner.append({"name": name, "id": pl.get("id")})
            continue

        # Tag check to avoid accidental deletions (unless disabled)
        if require_tag and not _playlist_has_tag(pl, DESCRIPTION_TAG):
            skipped_no_tag.append({"name": name, "id": pl.get("id")})
            continue

        found.append(pl)

    result = {
        "requested_source_name": source_name,
        "requested_year": year,
        "dry_run": bool(dry_run),
        "found_count": len(found),
        "found_playlists": [{"name": p.get("name"), "id": p.get("id")} for p in found],
        "skipped_not_owner": skipped_not_owner,
        "skipped_no_tag": skipped_no_tag,
    }

    if dry_run:
        # return the preview without deleting
        return result

    # Confirm unless forced
    if not force:
        # interactive confirmation; return as aborted if not confirmed
        print("The following playlists will be unfollowed (deleted from your library):")
        for p in found:
            print(f"  - {p.get('name')}  (id={p.get('id')})")
        ans = input("Type 'yes' to confirm deletion: ").strip().lower()
        if ans != "yes":
            result["aborted"] = True
            return result

    # Perform actual unfollow (delete) operations
    deleted = []
    failed = []
    for pl in found:
        try:
            _unfollow_playlist(access_token, pl["id"])
            deleted.append({"name": pl.get("name"), "id": pl.get("id")})
        except Exception as e:
            failed.append({"name": pl.get("name"), "id": pl.get("id"), "error": str(e)})

    result.update({
        "deleted_count": len(deleted),
        "deleted_playlists": deleted,
        "failed": failed,
    })
    return result


def split_playlist_by_year(source_url_or_id: str, make_public: bool = False) -> dict:
    """
    Read `source_url_or_id`, bucket tracks by album year, create/reuse playlists per year,
    add missing tracks, and return a summary dict describing what happened.
    """
    token_json = _ensure_token()
    access_token = token_json["access_token"]

    user_id = _current_user_id(access_token)

    source_id = _parse_playlist_id(source_url_or_id)
    source = _get_playlist(access_token, source_id)
    source_name = source.get("name", f"Playlist {source_id}")

    # Read items (tracks only), bucket by year
    buckets: Dict[str, List[str]] = {}
    skipped_episode = 0
    skipped_local = 0
    no_year = 0

    for it in _iter_pages(
        access_token,
        f"/playlists/{source_id}/tracks",
        params={
            "limit": 100,
            "fields": "items(is_local,track(album(release_date),type,uri),is_local),next",
            "additional_types": "track,episode",
        },
    ):
        if it.get("is_local"):
            skipped_local += 1
            continue
        track = it.get("track")
        if not track:
            continue
        if track.get("type") != "track":
            skipped_episode += 1
            continue
        tup = _track_uri_and_year(it)
        if not tup:
            no_year += 1
            continue
        uri, year = tup
        if not year:
            no_year += 1
            continue
        buckets.setdefault(year, [])
        buckets[year].append(uri)

    # De-dup within each year while preserving order
    for y in list(buckets.keys()):
        uniq = list(dict.fromkeys(buckets[y]))
        buckets[y] = uniq

    # For each year, create or reuse destination playlist and add missing tracks
    created = []
    updated = []
    per_year_added: Dict[str, int] = {}

    for year in sorted(buckets.keys()):
        desired_name = f"From {source_name}: {year}"
        description = (
            f'Auto-generated from "{source_name}" on {time.strftime("%Y-%m-%d")} '
            f"(year = {year}). {DESCRIPTION_TAG}"
        )
        dest_id = _find_user_playlist_by_name(access_token, user_id, desired_name)
        if dest_id is None:
            dest_id = _create_playlist(access_token, user_id, desired_name, description, public=make_public)
            created.append(desired_name)
            existing = set()
        else:
            existing = set(_get_playlist_track_uris(access_token, dest_id))

        to_add = [u for u in buckets[year] if u not in existing]
        if to_add:
            _add_items_in_batches(access_token, dest_id, to_add)
            updated.append(desired_name)
            per_year_added[year] = len(to_add)
        else:
            per_year_added[year] = 0

    # Build the summary dict
    total_added = sum(per_year_added.values())
    summary = {
        "source_playlist_id": source_id,
        "source_playlist_name": source_name,
        "years_found": sorted(list(buckets.keys())),
        "per_year_source_count": {y: len(buckets[y]) for y in buckets},
        "created_playlists": created,               # list of playlist names created
        "updated_playlists": updated,               # list of playlist names that received additions
        "per_year_added": per_year_added,           # year -> number of tracks added
        "total_tracks_added": total_added,
        "skipped_episodes": skipped_episode,
        "skipped_local_files": skipped_local,
        "tracks_missing_year": no_year,
    }

    return summary