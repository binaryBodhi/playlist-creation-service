import http.server
import queue
import urllib.parse
import socket
import threading
import webbrowser
import time

from .constants import REDIRECT_URI


class _AuthHandler(http.server.BaseHTTPRequestHandler):
    """
    Minimal handler to capture ?code=... from the redirect and put it on a queue.
    """

    queue_ref: "queue.Queue[str]" = None  # type: ignore

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != urllib.parse.urlparse(REDIRECT_URI).path:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found.")
            return

        qs = urllib.parse.parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        error = qs.get("error", [None])[0]

        self.send_response(200)
        self.end_headers()
        if code:
            self.wfile.write(b"You may close this tab and return to the app. Auth code received.")
            _AuthHandler.queue_ref.put(code)
        elif error:
            self.wfile.write(f"Authorization error: {error}".encode("utf-8"))
            _AuthHandler.queue_ref.put_nowait("")  # signal error
        else:
            self.wfile.write(b"No code in response.")
            _AuthHandler.queue_ref.put_nowait("")

    def log_message(self, format, *args):
        # Keep console quieter
        return


def _pick_loopback_port(host="127.0.0.1") -> int:
    # If the configured redirect has a specific port, use that; else pick a free one.
    parsed = urllib.parse.urlparse(REDIRECT_URI)
    if parsed.port:
        return parsed.port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _run_temp_server_and_wait_for_code(expected_state: str, auth_url: str, timeout: int = 300) -> str:
    global REDIRECT_URI
    q: "queue.Queue[str]" = queue.Queue()
    _AuthHandler.queue_ref = q

    # Ensure redirect host/port align with REDIRECT_URI
    parsed = urllib.parse.urlparse(REDIRECT_URI)
    host = parsed.hostname or "127.0.0.1"
    port = _pick_loopback_port(host)

    # Recompose REDIRECT_URI with the chosen port if none was specified
    # global REDIRECT_URI
    if parsed.port is None:
        REDIRECT_URI = f"{parsed.scheme}://{host}:{port}{parsed.path}"

    server = http.server.HTTPServer((host, port), _AuthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        print(f"[Auth] Opening browser for Spotify login…")
        print(f"[Auth] If it doesn’t open automatically, visit:\n{auth_url}\n")
        webbrowser.open(auth_url, new=1, autoraise=True)

        # Wait for code (or timeout)
        start = time.time()
        while True:
            try:
                code = q.get(timeout=0.5)
                server.shutdown()
                break
            except queue.Empty:
                if time.time() - start > timeout:
                    server.shutdown()
                    raise TimeoutError("Timed out waiting for Spotify authorization code.")
        if not code:
            raise RuntimeError("Failed to retrieve authorization code (empty).")
        return code
    finally:
        try:
            server.server_close()
        except Exception:
            pass

