#!/usr/bin/env python3
"""Zundamon standby speaker server.

Serves a standby page that subscribes to Server-Sent Events.
Muse pushes a phrase slug (e.g. "ryoukai") via POST /push?key=SECRET
and every connected page plays the matching VOICEVOX sample.
Samples are served from the samples-voicevox folder.
"""
import json, os, pathlib, queue, secrets, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = pathlib.Path.home()
KIT_DIR = pathlib.Path(__file__).resolve().parent.parent
SAMPLES_DIR = pathlib.Path(os.environ.get("ZUNDAMON_SAMPLES_DIR", KIT_DIR/"samples-voicevox"))
WORKDIR = pathlib.Path(os.environ.get("ZUNDAMON_WORKDIR", HOME/".zundamon-speaker"))
PORT = int(os.environ.get("ZUNDAMON_PORT", "8765"))
WORKDIR.mkdir(parents=True, exist_ok=True)

KEY_FILE = WORKDIR/"push_key.txt"
if KEY_FILE.exists():
    PUSH_KEY = KEY_FILE.read_text().strip()
else:
    PUSH_KEY = secrets.token_hex(16)
    KEY_FILE.write_text(PUSH_KEY)

man = json.loads((SAMPLES_DIR/"manifest.json").read_text(encoding="utf-8"))
SAMPLES = {}
for m in man:
    SAMPLES[m["slug"]] = {"text": m["text"], "cat": m["category"], "idx": m["index"], "file": m["file"]}
SAMPLES["zunda-on"] = {"text": "ずんだオンにしたのだ", "cat": "トリガー", "idx": 90, "file": "zunda-on.mp3"}
FILES = {v["file"] for v in SAMPLES.values()}

clients = []
clients_lock = threading.Lock()

def broadcast(obj):
    data = json.dumps(obj, ensure_ascii=False)
    with clients_lock:
        dead = []
        for q in clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            clients.remove(q)

PAGE_FILE = pathlib.Path(__file__).resolve().parent.parent/"page"/"standby_sse_template.html"
if not PAGE_FILE.exists():
    raise SystemExit(f"standby page template not found: {PAGE_FILE}")
PAGE = PAGE_FILE.read_text(encoding="utf-8")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = PAGE.replace("__SAMPLES_JSON__", json.dumps(SAMPLES, ensure_ascii=False))
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/samples/"):
            name = self.path[len("/samples/"):]
            if name in FILES and (SAMPLES_DIR/name).exists():
                body = (SAMPLES_DIR/name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        elif self.path == "/keepalive.mp3":
            p = WORKDIR/"keepalive.mp3"
            if p.exists():
                body = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        elif self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            q = queue.Queue(maxsize=100)
            with clients_lock:
                clients.append(q)
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        data = q.get(timeout=20)
                        self.wfile.write(f"data: {data}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with clients_lock:
                    if q in clients:
                        clients.remove(q)
        elif self.path == "/health":
            with clients_lock:
                n = len(clients)
            body = json.dumps({"ok": True, "clients": n}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.startswith("/push"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            if qs.get("key", [""])[0] != PUSH_KEY:
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8", "replace").strip()
            slug = raw
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    slug = obj.get("slug", "")
            except Exception:
                pass
            if slug in SAMPLES:
                broadcast({"slug": slug})
                body = json.dumps({"ok": True, "slug": slug}).encode()
                self.send_response(200)
            else:
                body = json.dumps({"ok": False, "error": "unknown slug", "slug": slug}).encode()
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"zundamon speaker server on 127.0.0.1:{PORT}, samples={len(SAMPLES)}", flush=True)
    server.serve_forever()
