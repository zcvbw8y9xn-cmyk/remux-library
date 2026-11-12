"""
Private local-only server for Remux Vault desktop app.
- Binds strictly to 127.0.0.1 (unreachable from network/internet)
- Protected by per-launch random session token
- Provides live library API + one-click Sync Now endpoint running run_daily.sh
"""

import argparse
import csv
import gzip
import http.cookies
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(PROJECT_DIR, "remux_library.csv")
HTML_FILE = os.path.join(PROJECT_DIR, "index.html")
SYNC_SCRIPT = os.path.join(PROJECT_DIR, "run_daily.sh")
LOG_FILE = os.path.join(PROJECT_DIR, "cron.log")
CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BRAVE_BIN = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CHROME_PROFILE = os.path.join(PROJECT_DIR, ".app_chrome_profile")


def _launch_browser_window(url: str):
    """Launch the private app window natively on arm64 (avoiding slow Rosetta x86_64)."""
    browser_bin = CHROME_BIN if os.path.exists(CHROME_BIN) else (BRAVE_BIN if os.path.exists(BRAVE_BIN) else None)
    if browser_bin:
        cmd = [
            "/usr/bin/arch",
            "-arm64",
            browser_bin,
            f"--app={url}",
            f"--user-data-dir={CHROME_PROFILE}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-background-networking",
            "--disable-sync",
            "--metrics-recording-only",
        ]
        return subprocess.Popen(cmd)
    subprocess.run(["open", url], check=False)
    return None

DEFAULT_PORT = 58239
TOKEN_FILE = os.path.join(PROJECT_DIR, ".app_token")


def _get_persistent_token() -> str:
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                tok = f.read().strip()
                if len(tok) >= 16:
                    return tok
        except Exception:
            pass
    tok = secrets.token_urlsafe(24)
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(tok)
        os.chmod(TOKEN_FILE, 0o600)
    except Exception:
        pass
    return tok


APP_TOKEN = _get_persistent_token()

sync_lock = threading.Lock()
sync_state = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "exit_code": None,
    "phase": "Idle",
    "log_lines": deque(maxlen=250),
}


def read_library_payload() -> dict:
    movies = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            movies = list(csv.DictReader(f))
    mtime = (
        datetime.fromtimestamp(os.path.getmtime(CSV_FILE)).strftime("%Y-%m-%d %H:%M")
        if os.path.exists(CSV_FILE)
        else "Never"
    )
    return {
        "movies": movies,
        "total": len(movies),
        "uhd": sum(1 for m in movies if "4K" in m.get("Quality", "")),
        "best_1080p": sum(1 for m in movies if "1080p Best" in m.get("Best Quality?", "")),
        "dvd": sum(1 for m in movies if "DVD" in m.get("Quality", "")),
        "last_updated": mtime,
    }


_cache_lock = threading.Lock()
_html_cache = {"mtime_ns": -1, "raw": b"", "gz": b""}
_data_cache = {"mtime_ns": -1, "raw": b"", "gz": b""}


def _get_cached_html() -> tuple[bytes, bytes]:
    mtime_ns = os.stat(HTML_FILE).st_mtime_ns
    with _cache_lock:
        if _html_cache["mtime_ns"] != mtime_ns:
            with open(HTML_FILE, "rb") as f:
                raw = f.read()
            _html_cache["raw"] = raw
            _html_cache["gz"] = gzip.compress(raw, compresslevel=6)
            _html_cache["mtime_ns"] = mtime_ns
        return _html_cache["raw"], _html_cache["gz"]


def _get_cached_data_json() -> tuple[bytes, bytes]:
    mtime_ns = os.stat(CSV_FILE).st_mtime_ns if os.path.exists(CSV_FILE) else 0
    with _cache_lock:
        if _data_cache["mtime_ns"] != mtime_ns:
            raw = json.dumps(
                read_library_payload(), ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            _data_cache["raw"] = raw
            _data_cache["gz"] = gzip.compress(raw, compresslevel=6)
            _data_cache["mtime_ns"] = mtime_ns
        return _data_cache["raw"], _data_cache["gz"]


def detect_phase(line: str) -> str:
    low = line.lower()
    if "scraping x.com" in low or "remux file link hunter" in low:
        return "Scraping X.com..."
    if "checking" in low and "link(s)" in low:
        return "Verifying links..."
    if "syncing to google sheet" in low:
        return "Updating Google Sheet..."
    if "updating web dashboard" in low:
        return "Rebuilding dashboard..."
    if "syncing changes to github" in low:
        return "Pushing to GitHub..."
    if "all done" in low:
        return "Completed"
    return sync_state["phase"]


def run_sync_worker():
    try:
        proc = subprocess.Popen(
            ["/bin/bash", SYNC_SCRIPT],
            cwd=PROJECT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            assert proc.stdout is not None
            for line in proc.stdout:
                lf.write(line)
                lf.flush()
                clean = line.rstrip("\n")
                if clean:
                    sync_state["log_lines"].append(clean)
                    sync_state["phase"] = detect_phase(clean)
        rc = proc.wait()
        sync_state["exit_code"] = rc
        sync_state["phase"] = "Completed" if rc == 0 else f"Failed (exit {rc})"
    except Exception as exc:
        sync_state["log_lines"].append(f"Error: {exc}")
        sync_state["exit_code"] = 1
        sync_state["phase"] = f"Error: {exc}"
    finally:
        sync_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sync_state["running"] = False
        sync_lock.release()


class RemuxAppHandler(BaseHTTPRequestHandler):
    server_version = "RemuxVaultLocal/1.0"

    def log_message(self, format, *args):
        return

    def _is_authorized(self) -> bool:
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if qs.get("token", [None])[0] == APP_TOKEN:
            return True
        if self.headers.get("X-App-Token") == APP_TOKEN:
            return True
        raw_cookie = self.headers.get("Cookie", "")
        if raw_cookie:
            c = http.cookies.SimpleCookie()
            c.load(raw_cookie)
            if "rv_token" in c and c["rv_token"].value == APP_TOKEN:
                return True
        return False

    def _send_bytes(self, status: int, content_type: str, raw_bytes: bytes, gz_bytes: bytes | None = None, extra_headers=None):
        accept_enc = self.headers.get("Accept-Encoding", "")
        use_gz = gz_bytes is not None and "gzip" in accept_enc
        body = gz_bytes if use_gz else raw_bytes
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        if use_gz:
            self.send_header("Content-Encoding", "gzip")
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send_bytes(status, "application/json; charset=utf-8", body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html") and not self._is_authorized():
            self.send_response(302)
            self.send_header("Location", f"/?token={APP_TOKEN}")
            self.send_header("Set-Cookie", f"rv_token={APP_TOKEN}; HttpOnly; SameSite=Strict; Path=/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if not self._is_authorized():
            self.send_error(403, "Forbidden: private local session token required")
            return

        if parsed.path in ("/", "/index.html"):
            if not os.path.exists(HTML_FILE):
                self.send_error(404, "index.html not found")
                return
            raw_bytes, gz_bytes = _get_cached_html()
            self._send_bytes(
                200,
                "text/html; charset=utf-8",
                raw_bytes,
                gz_bytes,
                extra_headers=[("Set-Cookie", f"rv_token={APP_TOKEN}; HttpOnly; SameSite=Strict; Path=/")],
            )
            return

        if parsed.path == "/api/data":
            raw_bytes, gz_bytes = _get_cached_data_json()
            self._send_bytes(200, "application/json; charset=utf-8", raw_bytes, gz_bytes)
            return

        if parsed.path == "/api/sync/status":
            self._send_json(
                200,
                {
                    "running": sync_state["running"],
                    "started_at": sync_state["started_at"],
                    "finished_at": sync_state["finished_at"],
                    "exit_code": sync_state["exit_code"],
                    "phase": sync_state["phase"],
                    "log_tail": list(sync_state["log_lines"])[-80:],
                },
            )
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        if not self._is_authorized():
            self.send_error(403, "Forbidden")
            return

        parsed = urlparse(self.path)
        if parsed.path == "/api/sync":
            if not sync_lock.acquire(blocking=False):
                self._send_json(409, {"started": False, "message": "Sync already running"})
                return
            sync_state["running"] = True
            sync_state["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sync_state["finished_at"] = None
            sync_state["exit_code"] = None
            sync_state["phase"] = "Starting sync..."
            sync_state["log_lines"].clear()
            t = threading.Thread(target=run_sync_worker, daemon=True)
            t.start()
            self._send_json(202, {"started": True, "phase": sync_state["phase"]})
            return

        self.send_error(404, "Not found")


STATE_FILE = os.path.join(PROJECT_DIR, ".app_state.json")


def _try_reuse_running_app() -> bool:
    """If an existing local app_server is alive, reopen its Chrome app window and exit cleanly."""
    if not os.path.exists(STATE_FILE):
        return False
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            st = json.load(f)
        pid = int(st.get("pid", 0))
        port = int(st.get("port", 0))
        token = st.get("token", "")
        if pid <= 0 or port <= 0 or not token:
            return False
        os.kill(pid, 0)
        import urllib.request
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/sync/status",
            headers={"X-App-Token": token},
        )
        urllib.request.urlopen(req, timeout=1.5).read()
        existing_url = f"http://127.0.0.1:{port}/?token={token}"
        _launch_browser_window(existing_url)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Private local Remux Vault app server")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--launch-chrome", action="store_true")
    args = parser.parse_args()

    if args.launch_chrome and _try_reuse_running_app():
        return

    # Bind strictly to 127.0.0.1 loopback so nothing external can connect
    bind_port = args.port if args.port > 0 else DEFAULT_PORT
    try:
        server = ThreadingHTTPServer(("127.0.0.1", bind_port), RemuxAppHandler)
    except OSError:
        server = ThreadingHTTPServer(("127.0.0.1", 0), RemuxAppHandler)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/?token={APP_TOKEN}"
    print(f"🔒 Remux Vault private local app running at http://127.0.0.1:{port}/")

    if args.launch_chrome:
        os.makedirs(CHROME_PROFILE, mode=0o700, exist_ok=True)
        os.chmod(CHROME_PROFILE, 0o700)
        with open(STATE_FILE, "w", encoding="utf-8") as sf:
            json.dump({"pid": os.getpid(), "port": port, "token": APP_TOKEN}, sf)
        os.chmod(STATE_FILE, 0o600)

        def _launch_ui():
            _launch_browser_window(url)

        threading.Thread(target=_launch_ui, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if os.path.exists(STATE_FILE):
            try:
                os.remove(STATE_FILE)
            except OSError:
                pass


if __name__ == "__main__":
    main()
