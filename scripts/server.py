#!/usr/bin/env python3
"""Zundamon standby speaker server.

Serves a standby page that subscribes to Server-Sent Events.
Muse pushes a phrase slug (e.g. "ryoukai") via POST /push?key=SECRET
and every connected page plays the matching VOICEVOX sample.
Samples are served from the samples-voicevox folder.
"""
import json, pathlib, queue, secrets, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = pathlib.Path.home()
SAMPLES_DIR = HOME/"workspace/your_files/zundamon-talk-prototype/samples-voicevox"
WORKDIR = HOME/"workspace/zundamon-speaker"
PORT = 8765

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

PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ずんだもん待機ページ</title>
<style>
*{box-sizing:border-box} body{margin:0;font-family:system-ui,sans-serif;background:#f3f8f0;color:#22301f}
.wrap{max-width:640px;margin:0 auto;padding:20px 16px 44px}
.card{background:#fff;border:1px solid #d9e6d2;border-radius:16px;padding:16px;margin-top:14px}
.sub{color:#5a6b55;font-size:13px;line-height:1.7}
button{font:inherit;border:0;border-radius:999px;padding:12px 14px;cursor:pointer;background:#e7f2df;color:#22301f}
button:active{transform:scale(.98)}
.primary{background:#67b34a;color:#fff;font-weight:800;font-size:17px;width:100%;padding:16px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.grid button{font-size:14px;padding:12px 6px}
.playing{outline:3px solid #67b34a}
h2{font-size:16px;margin:18px 0 10px}
#now{font-weight:800;font-size:17px}
#log{font-size:12px;line-height:1.7;white-space:pre-wrap;word-break:break-all}
.lamp{display:inline-block;width:12px;height:12px;border-radius:50%;background:#c0392b;vertical-align:middle;margin-right:6px}
.lamp.on{background:#67b34a}
</style></head><body><div class="wrap">
<h1 style="font-size:22px">ずんだもん待機ページ</h1>
<p class="sub">声は本物のVOICEVOX ずんだもん（ノーマル）なのだ。クレジット：VOICEVOX:ずんだもん。</p>
<div class="card">
<p style="margin:0 0 10px"><span class="lamp" id="lamp"></span><span id="conn">接続中…</span></p>
<button class="primary" id="enableBtn">音を有効にする（最初に1回だけタップ）</button>
<p class="sub" id="status">有効化すると確認で「了解なのだ」が鳴るのだ。その後は、モコ太郎から合図が届くたびに、対応するフレーズが自動で鳴るのだ。このページは開いたまま、別アプリに切り替えて大丈夫なのだ。</p>
<p id="now">待機中なのだ</p>
<button id="stopBtn" style="width:100%">止める</button>
</div>
<div id="sections"></div>
<div class="card"><h2 style="margin-top:0">ログ</h2><div id="log"></div></div>
<audio id="player" preload="auto"></audio>
<audio id="keepalive" preload="auto" loop src="/keepalive.mp3"></audio>
<script>
const SAMPLES = __SAMPLES_JSON__;
const player = document.getElementById('player');
const keep = document.getElementById('keepalive');
const logEl = document.getElementById('log');
const nowEl = document.getElementById('now');
let enabled = false;
let playing = false;
const playQueue = [];
function log(m){ const t=new Date().toLocaleTimeString('ja-JP'); logEl.textContent="["+t+"] "+m+"\\n"+logEl.textContent; }
function enqueue(slug, why){
  if(!SAMPLES[slug]){ log("知らない合図だったのだ："+slug); return; }
  playQueue.push({slug:slug, why:why});
  pump();
}
function pump(){
  if(playing || playQueue.length===0) return;
  const item = playQueue.shift();
  const s = SAMPLES[item.slug];
  playing = true;
  document.querySelectorAll('button[data-key]').forEach(b=>b.classList.toggle('playing', b.dataset.key===item.slug));
  nowEl.textContent = "再生中："+s.text;
  player.src = "/samples/"+s.file;
  player.play().then(()=>log(item.why+"："+s.text)).catch(e=>{ log("再生できませんでした："+s.text+" / "+e.name); playing=false; pump(); });
}
player.addEventListener('ended', ()=>{ playing=false; document.querySelectorAll('button[data-key]').forEach(b=>b.classList.remove('playing')); nowEl.textContent="待機中なのだ"; pump(); });
player.addEventListener('error', ()=>{ if(playing){ playing=false; pump(); } });
const cats = [];
Object.values(SAMPLES).forEach(s=>{ if(!cats.includes(s.cat)) cats.push(s.cat); });
const sec = document.getElementById('sections');
cats.forEach(cat=>{
  const h=document.createElement('h2'); h.textContent=cat; sec.appendChild(h);
  const g=document.createElement('div'); g.className='grid';
  Object.keys(SAMPLES).filter(k=>SAMPLES[k].cat===cat).sort((a,b)=>SAMPLES[a].idx-SAMPLES[b].idx).forEach(k=>{
    const b=document.createElement('button'); b.textContent=SAMPLES[k].text; b.dataset.key=k;
    b.addEventListener('click', ()=>{ enabled=true; enqueue(k, "タップ再生"); });
    g.appendChild(b);
  });
  sec.appendChild(g);
});
document.getElementById('enableBtn').addEventListener('click', ()=>{
  enabled = true;
  document.getElementById('status').textContent = "音が有効になったのだ。合図が来たら自動で鳴るのだ。このまま別アプリに切り替えて大丈夫なのだ。";
  keep.play().then(()=>log("無音の居座り再生を開始したのだ")).catch(e=>log("居座り再生は失敗したのだ："+e.name));
  enqueue("ryoukai", "有効化の確認再生");
});
document.getElementById('stopBtn').addEventListener('click', ()=>{ player.pause(); keep.pause(); playQueue.length=0; playing=false; nowEl.textContent="止めたのだ"; log("止めたのだ"); });
const es = new EventSource("/events");
es.onopen = ()=>{ document.getElementById('lamp').classList.add('on'); document.getElementById('conn').textContent="合図の接続がつながっているのだ"; log("合図の接続がつながったのだ"); };
es.onerror = ()=>{ document.getElementById('lamp').classList.remove('on'); document.getElementById('conn').textContent="接続が切れたのでつなぎ直しているのだ…"; log("合図の接続が切れたのだ。再接続を試みるのだ"); };
es.onmessage = (ev)=>{
  try{
    const obj = JSON.parse(ev.data);
    if(obj.slug){
      log("合図が届いたのだ："+obj.slug);
      if(enabled) enqueue(obj.slug, "プッシュ再生");
      else log("まだ音が有効になっていないので鳴らさなかったのだ");
    }
  }catch(e){ log("合図の解析に失敗したのだ"); }
};
document.addEventListener('visibilitychange', ()=>{ log(document.hidden ? "ページが背面に回ったのだ" : "ページが前面に戻ったのだ"); });
log("待機ページを読み込んだのだ");
</script></div></body></html>
"""

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
