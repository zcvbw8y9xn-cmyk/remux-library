"""
Private local-only server for Remux Vault desktop app.
- Binds strictly to 127.0.0.1 (unreachable from network/internet)
- Protected by per-launch random session token
- Provides live library API + one-click Sync Now endpoint running run_daily.sh
"""

import argparse
import csv
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
CHROME_PROFILE = os.path.join(PROJECT_DIR, ".app_chrome_profile")

APP_TOKEN = secrets.token_urlsafe(24)

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

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._is_authorized():
            self.send_error(403, "Forbidden: private local session token required")
            return

        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            if not os.path.exists(HTML_FILE):
                self.send_error(404, "index.html not found")
                return
            with open(HTML_FILE, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Set-Cookie",
                f"rv_token={APP_TOKEN}; HttpOnly; SameSite=Strict; Path=/",
            )
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if parsed.path == "/api/data":
            self._send_json(200, read_library_payload())
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


def main():
    parser = argparse.ArgumentParser(description="Private local Remux Vault app server")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--launch-chrome", action="store_true")
    args = parser.parse_args()

    # Bind strictly to 127.0.0.1 loopback so nothing external can connect
    server = ThreadingHTTPServer(("127.0.0.1", args.port), RemuxAppHandler)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/?token={APP_TOKEN}"
    print(f"🔒 Remux Vault private local app running at http://127.0.0.1:{port}/")

    if args.launch_chrome:
        os.makedirs(CHROME_PROFILE, mode=0o700, exist_ok=True)
        os.chmod(CHROME_PROFILE, 0o700)
        def _launch_ui():
            time.sleep(0.4)
            if os.path.exists(CHROME_BIN):
                proc = subprocess.Popen(
                    [
                        CHROME_BIN,
                        f"--app={url}",
                        f"--user-data-dir={CHROME_PROFILE}",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ]
                )
                proc.wait()
                server.shutdown()
            else:
                subprocess.run(["open", url], check=False)

        threading.Thread(target=_launch_ui, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
