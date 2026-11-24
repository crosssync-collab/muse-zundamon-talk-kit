#!/usr/bin/env python3
"""Zundamon standby speaker server.

Serves a standby page that subscribes to Server-Sent Events.
Muse pushes a phrase slug (e.g. "ryoukai") via POST /push?key=SECRET
and every connected page plays the matching VOICEVOX sample.
Samples are served from the samples-voicevox folder.
"""
import collections, json, os, pathlib, queue, secrets, threading, time
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

# Every pushed cue gets a sequence number so a reconnected page can
# recover cues it missed: the server keeps the most recent events and
# replays the ones after the client's Last-Event-ID, and /state lets
# the page check the latest cue explicitly.
event_lock = threading.Lock()
event_seq = 0
last_event = {"seq": 0, "slug": None, "ts": 0}
recent_events = collections.deque(maxlen=50)

DIAG_FILE = WORKDIR/"diag.log"
diag_lock = threading.Lock()

def broadcast(obj):
    with clients_lock:
        dead = []
        for q in clients:
            try:
                q.put_nowait(obj)
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
                # Replay cues the client missed while disconnected.
                # EventSource sends Last-Event-ID automatically on
                # reconnect when earlier events carried an id: field.
                last_id = 0
                try:
                    last_id = int(self.headers.get("Last-Event-ID") or 0)
                except ValueError:
                    last_id = 0
                if last_id:
                    with event_lock:
                        missed = [e for e in recent_events if e["seq"] > last_id]
                    for e in missed:
                        self.wfile.write(f"id: {e['seq']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n".encode())
                    if missed:
                        self.wfile.flush()
                while True:
                    try:
                        evt = q.get(timeout=20)
                        self.wfile.write(f"id: {evt['seq']}\ndata: {json.dumps(evt, ensure_ascii=False)}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with clients_lock:
                    if q in clients:
                        clients.remove(q)
        elif self.path == "/state":
            with event_lock:
                body = json.dumps(last_event).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/diag"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            if qs.get("key", [""])[0] != PUSH_KEY:
                self.send_error(403)
                return
            try:
                n = max(1, min(2000, int(qs.get("n", ["200"])[0])))
            except ValueError:
                n = 200
            lines = []
            if DIAG_FILE.exists():
                lines = DIAG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
            body = ("\n".join(lines) + ("\n" if lines else "")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
                global event_seq
                with event_lock:
                    event_seq += 1
                    evt = {"slug": slug, "seq": event_seq, "ts": time.time()}
                    last_event.update(evt)
                    recent_events.append(evt)
                broadcast(evt)
                body = json.dumps({"ok": True, "slug": slug, "seq": evt["seq"]}).encode()
                self.send_response(200)
            else:
                body = json.dumps({"ok": False, "error": "unknown slug", "slug": slug}).encode()
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/diag":
            length = int(self.headers.get("Content-Length", 0))
            if length > 16384:
                self.send_error(413)
                return
            raw = self.rfile.read(length).decode("utf-8", "replace").strip()
            rec = {"srv_ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "raw": raw}
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    rec = {"srv_ts": rec["srv_ts"], **obj}
            except Exception:
                pass
            with diag_lock:
                with DIAG_FILE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if DIAG_FILE.stat().st_size > 1_000_000:
                    kept = DIAG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
                    DIAG_FILE.write_text("\n".join(kept) + "\n", encoding="utf-8")
            body = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"zundamon speaker server on 127.0.0.1:{PORT}, samples={len(SAMPLES)}", flush=True)
    server.serve_forever()
