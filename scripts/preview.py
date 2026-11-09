"""Serve site/ locally, open it in the default browser, and exit once the tab is closed.

Usage (from any checkout or worktree):

    python scripts/preview.py [--port N] [--no-browser]

How it cleans up after itself: every HTML page it serves gets a one-line script
that opens a Server-Sent Events stream to /__preview__/events. The browser keeps
that connection open for as long as the tab is open (background tabs included,
since it is a socket rather than a timer), and drops it the moment the tab closes.
When no page has been connected for GRACE_SECONDS, the server shuts down and frees
the port. Reloading is fine: the new page reconnects well inside the grace period.
The snippet is injected only into responses from this dev server; site/index.html
on disk, and so the deployed site, is never touched.

Running it again while a preview of the same site/ is already up just opens
another tab on the running server instead of starting a second one.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import select
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

SITE_DIR = (Path(__file__).resolve().parent.parent / "site").resolve()
HOST = "127.0.0.1"
PREFERRED_PORT = 8765
PORT_RANGE = 20                # try 8765..8784 before letting the OS pick
GRACE_SECONDS = 3.0            # how long with no open tab before exiting
STARTUP_TIMEOUT_SECONDS = 120  # exit if no tab ever connects (browser never opened)
APP_ID = "pollkadot-preview"
PREFIX = "/__preview__/"

# onerror closes the stream instead of letting EventSource retry. Otherwise a tab left open
# after the server stopped (Ctrl+C) would silently reattach to the next preview and keep it
# alive, e.g. a hidden T3 Code browser tab in another thread.
SNIPPET = (
    b"<script>/* injected by scripts/preview.py, not part of the site */"
    b"(()=>{try{const s=new EventSource('" + PREFIX.encode() + b"events');"
    b"s.onerror=()=>s.close()}catch(e){}})();</script>"
)

EXIT_OK = 0             # the tab closed, Ctrl+C, or handed off to a running preview
EXIT_NO_TAB = 2         # no tab ever connected; non-zero so the terminal stays open to show why


def same_dir(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def probe(port: int) -> dict | None:
    """Return the info of a preview server on this port, or None if there isn't one."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never via a proxy
    try:
        with opener.open(f"http://{HOST}:{port}{PREFIX}info", timeout=0.5) as r:
            info = json.loads(r.read().decode())
            return info if info.get("app") == APP_ID else None
    except Exception:
        return None


class Tracker:
    """Counts open tabs (live event streams) and decides when to shut down."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.clients = 0
        self.ever_connected = False
        self.last_seen = time.monotonic()
        self.stopping = threading.Event()

    def connect(self, label: str) -> None:
        with self.lock:
            self.clients += 1
            self.ever_connected = True
            print(f"preview: tab opened ({label}); {self.clients} open", flush=True)

    def disconnect(self, label: str) -> None:
        with self.lock:
            self.clients -= 1
            self.last_seen = time.monotonic()
            if not self.stopping.is_set():
                print(f"preview: tab closed ({label}); {self.clients} open", flush=True)

    def should_stop(self, started: float) -> str | None:
        with self.lock:
            now = time.monotonic()
            if self.clients > 0:
                return None
            if self.ever_connected and now - self.last_seen >= GRACE_SECONDS:
                return "browser tab closed"
            if not self.ever_connected and now - started >= STARTUP_TIMEOUT_SECONDS:
                return f"no browser tab connected within {STARTUP_TIMEOUT_SECONDS}s"
            return None


class Handler(http.server.SimpleHTTPRequestHandler):
    tracker: Tracker  # set on the class before serving

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE_DIR), **kwargs)

    # Always revalidate, so edits to index.html or data show up on a plain reload.
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_request(self, code="-", size="-") -> None:
        if isinstance(code, int) and code >= 400:
            super().log_request(code, size)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == PREFIX + "info":
            return self.send_json({"app": APP_ID, "root": str(SITE_DIR), "pid": os.getpid()})
        if path == PREFIX + "events":
            return self.stream_events()
        return super().do_GET()

    def send_json(self, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def stream_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.close_connection = True
        sock = self.connection
        ua = self.headers.get("User-Agent", "")
        label = "T3 Code browser" if "Electron/" in ua else "browser"
        self.tracker.connect(label)
        try:
            self.wfile.write(b"retry: 1000\n\n")
            self.wfile.flush()
            while not self.tracker.stopping.is_set():
                # A closed tab shows up as the socket becoming readable with EOF.
                readable, _, _ = select.select([sock], [], [], 1.0)
                if readable and not sock.recv(4096):
                    break
                # Periodic write as a second check, in case the close was a reset.
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except OSError:
            pass
        finally:
            self.tracker.disconnect(label)

    def send_head(self):
        """Serve HTML with the heartbeat snippet injected; everything else as usual."""
        fs_path = Path(self.translate_path(self.path))
        if fs_path.is_dir():
            if not self.path.split("?", 1)[0].endswith("/"):
                return super().send_head()  # let the base class redirect to add the slash
            fs_path = fs_path / "index.html"
        if fs_path.suffix.lower() not in (".html", ".htm") or not fs_path.is_file():
            return super().send_head()
        html = fs_path.read_bytes()
        idx = html.lower().rfind(b"</body>")
        html = html[:idx] + SNIPPET + html[idx:] if idx >= 0 else html + SNIPPET
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(html)
        return None


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    # SO_REUSEADDR on Windows lets two servers share a port; claim it exclusively instead.
    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def port_taken(port: int) -> bool:
    """Cheap local check. Probing a free port over HTTP costs ~2s on Windows (SYN retries)."""
    with socket.socket() as s:
        try:
            s.bind((HOST, port))
            return False
        except OSError:
            return True


def bind(port_arg: int | None) -> Server | int:
    """Bind a new server, or return the port of an existing preview of this same site."""
    ports = [port_arg] if port_arg else list(range(PREFERRED_PORT, PREFERRED_PORT + PORT_RANGE))
    for port in ports:
        if not port_taken(port):
            continue
        info = probe(port)
        if info and same_dir(info.get("root", ""), str(SITE_DIR)):
            return port
    for port in ports + ([] if port_arg else [0]):
        try:
            return Server((HOST, port), Handler)
        except OSError:
            continue
    sys.exit(f"preview: could not bind a port (tried {ports[0]}..{ports[-1]})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, help=f"port to use (default: first free from {PREFERRED_PORT})")
    ap.add_argument("--no-browser", action="store_true", help="don't open the browser")
    args = ap.parse_args()

    if not (SITE_DIR / "index.html").is_file():
        sys.exit(f"preview: {SITE_DIR / 'index.html'} not found")

    result = bind(args.port)
    if isinstance(result, int):
        url = f"http://{HOST}:{result}/"
        if args.no_browser:
            print(f"preview: already serving {SITE_DIR} at {url}")
        else:
            print(f"preview: already serving {SITE_DIR} at {url}; opening another tab.")
            webbrowser.open(url)
        return EXIT_OK

    server = result
    tracker = Handler.tracker = Tracker()
    url = f"http://{HOST}:{server.server_address[1]}/"
    print(f"preview: serving {SITE_DIR}")
    print(f"preview: {url}  (stops by itself a few seconds after the last tab closes; Ctrl+C to stop now)")
    sys.stdout.flush()

    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.25}, daemon=True)
    thread.start()
    if not args.no_browser:
        webbrowser.open(url)

    started = time.monotonic()
    code = EXIT_OK
    try:
        while (reason := tracker.should_stop(started)) is None:
            time.sleep(0.25)
        print(f"preview: {reason}; shutting down.")
        if not tracker.ever_connected:
            code = EXIT_NO_TAB
    except KeyboardInterrupt:
        print("preview: interrupted; shutting down.")
    finally:
        tracker.stopping.set()
        server.shutdown()
        server.server_close()
    return code


if __name__ == "__main__":
    sys.exit(main())
