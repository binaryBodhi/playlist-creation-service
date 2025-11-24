import json
from .llm_helpers import safe_invoke_tool, ask_llm_to_say_tool_result,call_llm_choose_tool

def speak(text: str) -> None:
    """Placeholder speak function. Replace with your TTS call."""
    # Example: save audio from TTS service and play, or call a local TTS engine.
    # For now, just print a visual marker.
    print("\n[SPEAKING]:", text, "\n")

def interactive_loop():
    print("Jarvis (Spotify) — type a command (or 'quit'):")
    while True:
        try:
            user = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if not user:
            continue
        if user.lower() in ("quit", "exit", "q"):
            print("Bye.")
            return

        try:
            decision = call_llm_choose_tool(user)
        except Exception as e:
            print("LLM error:", e)
            continue

        if decision.get("name") is None:
            # LLM did not choose a function; just print what it said
            print("[assistant]:", decision.get("text"))
            continue

        func_name = decision["name"]
        func_args = decision["args"]
        print(f"[debug] LLM decided to call: {func_name} with args {func_args}")

        # Call the actual tool (your API)
        try:
            tool_result = safe_invoke_tool(func_name, func_args)
        except Exception as e:
            # If tool failed, ask LLM to explain the error in user-friendly terms
            print("Tool error:", e)
            err_reply = f"Sorry — the operation failed: {e}"
            print(err_reply)
            continue

        # Ask LLM to generate a spoken reply summarizing the tool result
        try:
            reply_text = ask_llm_to_say_tool_result(user, func_name, func_args, tool_result)
        except Exception as e:
            # fallback: basic summary
            reply_text = f"Operation completed. Result: {json.dumps(tool_result, indent=2)[:400]}"
        print("[Jarvis]:", reply_text)
        # Optionally synthesize voice
        speak(reply_text)


if __name__ == "__main__":
    interactive_loop()