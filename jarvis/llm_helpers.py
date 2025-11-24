# llm_helpers.py
import json
import os
import pathlib

from ..apis.api import split_playlist_by_year, delete_year_playlists
from ..apis.constants import _get_openai_api_key

try:
    # new OpenAI client (openai >= 1.0.0)
    from openai import OpenAI  # type: ignore[import]
except Exception as e:
    raise RuntimeError(
        "Install the official OpenAI Python package (pip install openai) "
        "and use a version >=1.0.0. "
        f"Original error: {e}"
    ) from e

CHAT_MODEL = "gpt-4o-mini"
FUNCTIONS_PATH = pathlib.Path(__file__).parent / "jarvis_tools.json"

with FUNCTIONS_PATH.open("r", encoding="utf-8") as f:
    LLM_FUNCTIONS = json.load(f)

OPENAI_API_KEY = _get_openai_api_key()
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in the environment before running this script.")

# instantiate client once
client = OpenAI(api_key=OPENAI_API_KEY)


def call_llm_choose_tool(user_text: str) -> dict:
    """
    Ask the LLM which function/tool to call based on the user's text.
    Returns:
        { "name": <function_name_or_None>, "args": {...}, "raw_response": ... }
    """

    messages = [
        {"role": "system", "content": "You are Jarvis — a helpful assistant that maps user commands to available Spotify tools."},
        {
            "role": "system",
            "content": (
                "Available tools:\n"
                "1) spotify_split_playlist(source_playlist: str, make_public: bool)\n"
                "2) spotify_delete_year_playlists(source_name: str, year: Optional[str], dry_run: bool, force: bool, no_tag_check: bool)\n\n"
                "When the user asks for an operation on playlists, respond with a function call in JSON (using the provided schema). "
                "Only call a function when fully confident which one to use. "
                "If ambiguous, ask a clarifying question."
            )
        },
        {"role": "user", "content": user_text},
    ]

    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        tools=LLM_FUNCTIONS,
        tool_choice="auto",
        max_tokens=800,
        temperature=0.0,
    )

    # pick the first choice
    choice = resp.choices[0]

    #
    # If the model selected a tool call
    #
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        tool_call = choice.message.tool_calls[0]
        name = tool_call.function.name
        raw_args = tool_call.function.arguments

        try:
            args = json.loads(raw_args)
        except Exception:
            args = {"raw": raw_args}

        return {
            "name": name,
            "args": args,
            "raw_response": resp
        }

    #
    # No tool call — plain text reply
    #
    return {
        "name": None,
        "args": {},
        "text": choice.message.content or "",
        "raw_response": resp,
    }


def safe_invoke_tool(func_name: str, args: dict) -> dict:
    """
    Call the correct underlying Python function and return a dict result.
    """

    if func_name == "spotify_split_playlist":
        source = args.get("source_playlist") or args.get("source")
        if not source:
            raise ValueError("Missing 'source_playlist' argument.")
        make_public = bool(args.get("make_public", False))
        return split_playlist_by_year(source, make_public=make_public)

    elif func_name == "spotify_delete_year_playlists":
        source_name = args.get("source_name")
        if not source_name:
            raise ValueError("Missing 'source_name'.")
        year = args.get("year")
        dry_run = bool(args.get("dry_run", True))
        force = bool(args.get("force", False))
        no_tag_check = bool(args.get("no_tag_check", False))

        return delete_year_playlists(
            source_name=source_name,
            year=year,
            require_tag=(not no_tag_check),
            dry_run=dry_run,
            force=force,
        )

    else:
        raise ValueError(f"Unknown function: {func_name}")


def ask_llm_to_say_tool_result(user_text: str, tool_name: str, tool_args: dict, tool_result: dict) -> str:
    """
    Produce a short, spoken-style summary of the tool result.
    """
    messages = [
        {"role": "system", "content": "You are Jarvis. Polite, concise, slightly formal. Reply in 1–2 sentences."},
        {"role": "user", "content": user_text},
        {
            "role": "assistant",
            "content": f"I called the tool `{tool_name}` with args {json.dumps(tool_args)}."
        },
        {
            "role": "tool",
            "tool_call_id": "tool-result",
            "content": json.dumps(tool_result, default=str),
        },
        {
            "role": "user",
            "content": "Given the tool result above, produce a brief spoken reply summarizing the outcome."
        },
    ]

    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        max_tokens=200,
        temperature=0.3,
    )

    return resp.choices[0].message.content.strip()