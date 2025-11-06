import argparse
import time

from .oauth import _ensure_token
from typing import Dict, List

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

)

def split_playlist_by_year(source_url_or_id: str, make_public: bool = False):
    token_json = _ensure_token()
    access_token = token_json["access_token"]

    user_id = _current_user_id(access_token)

    source_id = _parse_playlist_id(source_url_or_id)
    source = _get_playlist(access_token, source_id)
    source_name = source.get("name", f"Playlist {source_id}")

    print(f"Source playlist: {source_name}")

    # Read items (tracks only), bucket by year
    buckets: Dict[str, List[str]] = {}
    skipped_episode = 0
    skipped_local = 0
    no_year = 0

    print("Reading source items…")
    #loop adds uri's of songs to bucket
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

    # De-duplicate songs from source playlist within each year
    for y in list(buckets.keys()):
        uniq = list(dict.fromkeys(buckets[y]))
        buckets[y] = uniq

    # For each year, create or reuse destination playlist and add missing tracks
    created = []
    updated = []
    for year in sorted(buckets.keys()):
        desired_name = f"From {source_name}: {year}"
        description = f'Auto-generated from "{source_name}" on {time.strftime("%Y-%m-%d")} (year = {year}).'
        dest_id = _find_user_playlist_by_name(access_token, user_id, desired_name)
        if dest_id is None:
            print(f"Creating playlist: {desired_name}")
            dest_id = _create_playlist(access_token, user_id, desired_name, description, public=make_public)
            created.append(desired_name)
            existing = set()
        else:
            print(f"Reusing playlist: {desired_name}")
            existing = set(_get_playlist_track_uris(access_token, dest_id))

        to_add = [u for u in buckets[year] if u not in existing]
        if to_add:
            print(f"  Adding {len(to_add)} tracks to {desired_name} …")
            _add_items_in_batches(access_token, dest_id, to_add)
            updated.append((desired_name, len(to_add)))
        else:
            print(f"  No new tracks to add for {desired_name}.")

    # Summary
    print("\n==== Summary ====")
    total_added = sum(n for _, n in updated) if updated else 0
    print(f"Years found: {', '.join(sorted(buckets.keys())) or 'None'}")
    for y in sorted(buckets.keys()):
        print(f"  {y}: {len(buckets[y])} unique tracks (source)")
    print(f"Created playlists: {len(created)}")
    print(f"Updated playlists: {len(updated)} (total tracks added: {total_added})")
    print(f"Skipped episodes: {skipped_episode}")
    print(f"Skipped local files: {skipped_local}")
    print(f"Tracks with missing year: {no_year}")

def main():
    parser = argparse.ArgumentParser(description="Create year-based playlists from a source Spotify playlist.")
    parser.add_argument("source_playlist", help="Source playlist URL or ID (e.g., https://open.spotify.com/playlist/...)")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Create public year-playlists (default is private).",
    )
    args = parser.parse_args()

    split_playlist_by_year(args.source_playlist, make_public=bool(args.public))