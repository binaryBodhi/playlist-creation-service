# playlist-creation-service

Split a Spotify playlist into per-year playlists and (optionally) remove the generated year playlists.

Requirements
- Python 3.10+
- requests (pip install requests)

Quick setup
- Export your Spotify app client id:

	export SPOTIFY_CLIENT_ID="your-client-id"

- On first run the tool performs OAuth and stores a token at ~/.spotify_year_splitter_token.json.

Usage
- Create / split playlists:

	python3 -m playlist-creation-service <SOURCE_PLAYLIST_URL_OR_ID>

	Use --public to create public playlists.

- Preview deletion of a specific year (dry-run is default):

	python3 -m playlist-creation-service --delete-year "SourceName" --year 2020

- Actually delete (unfollow) the matched playlist:

	python3 -m playlist-creation-service --delete-year "SourceName" --year 2020 --no-dry-run

Notes & safety
- Playlists created by this tool are named "From <SourceName>: <YYYY>" and include the tag
	[year-splitter] in their description. By default the delete mode only targets playlists
	you own and whose description contains that tag.
- Matching is case- and whitespace-sensitive. Use --no-tag-check to skip the description tag
	guard (risky). Use --force to skip interactive confirmation when deleting.

Troubleshooting
- "No matching playlists found to delete": verify exact playlist name, year, description tag,
	and that you're authenticated as the playlist owner.

LLM / Jarvis integration (optional)

- Files: `jarvis/llm_helpers.py` and `jarvis/jarvis_tools.json` define a small assistant
	that can map natural-language commands to the tool functions (e.g. `spotify_split_playlist`,
	`spotify_delete_year_playlists`).
- Dependencies: install the OpenAI client:

	```bash
	python3 -m pip install openai
	```

- Environment: set `OPENAI_API_KEY` before using the Jarvis tools. The LLM module
	will attempt to instantiate an OpenAI client on import and will raise if the key
	is missing. To avoid import-time failures, set the env var first:

	```bash
	export OPENAI_API_KEY="sk-..."
	```

- Usage: the `jarvis/` scripts provide a CLI mapping user text to function calls. Run
	or import the scripts in that folder to interact with the assistant. The JSON
	function schema is in `jarvis/jarvis_tools.json`.

- Safety: LLM-driven actions still call the same underlying functions that enforce
	ownership and description-tag checks for deletions. However, because the LLM can
	suggest actions, review any planned operation before confirming destructive steps.
