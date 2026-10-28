#!/usr/bin/env python3
"""Build the standalone standby page (single HTML) from the template.

Fills the template placeholders:
  __SAMPLES_JSON__ : {slug: {text, cat, idx, file, src=data-uri}} from manifest + mp3s
  __KEEPALIVE__    : data URI of a silent loop mp3 (keeps the page "playing")
  __SHEET_ID__     : your state spreadsheet id

Usage:
  python3 build_standby.py <template.html> <samples_dir> <keepalive.mp3> <sheet_id> <out.html>
"""
import base64, json, pathlib, sys

def main():
    template_path, samples_dir, keepalive, sheet_id, out_path = sys.argv[1:6]
    samples_dir = pathlib.Path(samples_dir)
    man = json.loads((samples_dir / "manifest.json").read_text(encoding="utf-8"))
    data = {}
    for m in man:
        b64 = base64.b64encode((samples_dir / m["file"]).read_bytes()).decode()
        data[m["slug"]] = {"text": m["text"], "cat": m["category"], "idx": m["index"],
                           "file": m["file"], "src": f"data:audio/mpeg;base64,{b64}"}
    html = pathlib.Path(template_path).read_text(encoding="utf-8")
    html = html.replace("__SAMPLES_JSON__", json.dumps(data, ensure_ascii=False))
    keep_b64 = base64.b64encode(pathlib.Path(keepalive).read_bytes()).decode()
    html = html.replace("__KEEPALIVE__", f"data:audio/mpeg;base64,{keep_b64}")
    html = html.replace("__SHEET_ID__", sheet_id)
    pathlib.Path(out_path).write_text(html, encoding="utf-8")
    print("built:", out_path, len(html), "bytes, samples:", len(data))

if __name__ == "__main__":
    main()
