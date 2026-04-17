# playlist_creation_service/cli.py
import argparse
import sys
import json
from .api import split_playlist_by_year, delete_year_playlists

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create or delete year-based playlists from a source Spotify playlist."
    )

    # Create/split mode
    parser.add_argument(
        "source_playlist",
        nargs="?",
        help="Source playlist URL or ID (required for create/split mode).",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Create public year-playlists (default: private).",
    )

    # Delete options
    mode = parser.add_argument_group("delete mode")
    mode.add_argument("--delete-all", metavar="SOURCE_NAME", help='Delete all year playlists created from this source name.')
    mode.add_argument("--delete-year", metavar="SOURCE_NAME", help='Delete one year-playlist for this source name (use with --year YYYY).')
    mode.add_argument("--year", metavar="YYYY", help="Year to delete with --delete-year.")
    mode.add_argument("--no-tag-check", action="store_true", help="Allow deletion even if DESCRIPTION_TAG is missing.")
    mode.add_argument("--dry-run", action="store_true", default=True, help="Preview deletions (default on).")
    mode.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="Actually delete matched playlists.")
    mode.add_argument("--force", action="store_true", help="Skip interactive confirmation when deleting.")

    args = parser.parse_args(argv)

    # Route: delete
    if args.delete_all or args.delete_year:
        if args.delete_year and not args.year:
            parser.error("--delete-year requires --year YYYY")
        source_name = args.delete_all or args.delete_year
        result = delete_year_playlists(
            source_name=source_name,
            year=args.year,
            require_tag=(not args.no_tag_check),
            dry_run=bool(args.dry_run),
            force=bool(args.force),
        )
        # CLI prints a user-friendly summary
        print(json.dumps(result, indent=2))
        return 0

    # Route: split/create
    if not args.source_playlist:
        args.source_playlist = input("Enter source playlist URL or ID: ").strip()

    result = split_playlist_by_year(args.source_playlist, make_public=bool(args.public))
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())