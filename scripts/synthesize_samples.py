#!/usr/bin/env python3
"""Synthesize all talk phrases with VOICEVOX (speaker 3 = Zundamon normal).

Rules encoded here:
- Endings are written WITHOUT the small tsu: なのだ / のだ (never なのだっ).
  VOICEVOX pronounces an added っ as an extra tsu; plain なのだ already
  ends short in Zundamon's voice.
- Per-sample QC: the reading (kana) must contain ノダ and must NOT contain
  ノダッ, and duration must be within 0.5-4.0 s.

Usage:
  1. Start the VOICEVOX engine: ./run --host 127.0.0.1 --port 50021
  2. python3 synthesize_samples.py <out_dir>
"""
import json, pathlib, subprocess, sys, urllib.parse, urllib.request

BASE = "http://127.0.0.1:50021"
SPEAKER = 3  # ずんだもん ノーマル

# (slug, file, category, text) — noun stems take なのだ, verb/adjective stems のだ.
PHRASES = [
    ("ohayou", "01_ohayou.mp3", "挨拶", "おはようなのだ"),
    ("konnichiwa", "02_konnichiwa.mp3", "挨拶", "こんにちはなのだ"),
    ("konbanwa", "03_konbanwa.mp3", "挨拶", "こんばんはなのだ"),
    ("otsukare", "04_otsukare.mp3", "挨拶", "おつかれさまなのだ"),
    ("oyasumi", "05_oyasumi.mp3", "挨拶", "おやすみなのだ"),
    ("ryoukai", "06_ryoukai.mp3", "了解", "了解なのだ"),
    ("wakatta", "07_wakatta.mp3", "了解", "わかったのだ"),
    ("makasete", "08_makasete.mp3", "了解", "ボクに任せてほしいのだ"),
    ("arigatou", "09_arigatou.mp3", "感謝・反応", "ありがとうなのだ"),
    ("sugoi", "10_sugoi.mp3", "感謝・反応", "すごいのだ"),
    ("yatta", "11_yatta.mp3", "感謝・反応", "やったのだ"),
    ("iikanji", "12_iikanji.mp3", "感謝・反応", "いい感じなのだ"),
    ("shiraberu", "13_shiraberu.mp3", "開始", "調べてみるのだ"),
    ("yattemiru", "14_yattemiru.mp3", "開始", "やってみるのだ"),
    ("tsukuttemiru", "15_tsukuttemiru.mp3", "開始", "作ってみるのだ"),
    ("kakunin", "16_kakunin.mp3", "開始", "確認するのだ"),
    ("yatteru", "17_yatteru.mp3", "途中", "今やってる途中なのだ"),
    ("mousukoshi", "18_mousukoshi.mp3", "途中", "もう少し待ってほしいのだ"),
    ("omatase", "19_omatase.mp3", "途中", "お待たせなのだ"),
    ("dekita", "20_dekita.mp3", "完了", "できたのだ"),
    ("owatta", "21_owatta.mp3", "完了", "終わったのだ"),
    ("mitsuketa", "22_mitsuketa.mp3", "完了", "見つけたのだ"),
    ("naoshita", "23_naoshita.mp3", "完了", "直しておいたのだ"),
    ("gomen", "24_gomen.mp3", "失敗", "ごめんなのだ、できなかったのだ"),
    ("mitsukaranai", "25_mitsukaranai.mp3", "失敗", "見つからなかったのだ"),
    ("mouichido", "26_mouichido.mp3", "失敗", "もう一度やってみるのだ"),
    ("dore", "27_dore.mp3", "お願い", "どれにするか教えてほしいのだ"),
    ("oshiete", "28_oshiete.mp3", "お願い", "分からないところを教えてほしいのだ"),
    ("logkudasai", "29_logkudasai.mp3", "お願い", "ログを貼ってほしいのだ"),
    ("daijoubu", "30_daijoubu.mp3", "励まし", "大丈夫なのだ"),
    ("yukkuri", "31_yukkuri.mp3", "励まし", "ゆっくりでいいのだ"),
    ("baibai", "32_baibai.mp3", "締め", "バイバイなのだ"),
    ("zunda-on", "zunda-on.mp3", "トリガー", "ずんだオンにしたのだ"),
]

def synth(text, mp3path):
    q = urllib.parse.urlencode({"text": text, "speaker": SPEAKER})
    req = urllib.request.Request(f"{BASE}/audio_query?{q}", method="POST")
    query = json.load(urllib.request.urlopen(req))
    kana = query.get("kana", "")
    req2 = urllib.request.Request(
        f"{BASE}/synthesis?speaker={SPEAKER}",
        data=json.dumps(query).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    wav = urllib.request.urlopen(req2).read()
    tmp = mp3path.with_suffix(".wav")
    tmp.write_bytes(wav)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), str(mp3path)], check=True)
    tmp.unlink()
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(mp3path)], capture_output=True, text=True)
    return kana, round(float(r.stdout.strip()), 2)

def main():
    outdir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "samples")
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    for i, (slug, file, cat, text) in enumerate(PHRASES, 1):
        kana, dur = synth(text, outdir / file)
        ok = ("ノダッ" not in kana) and ("ノダ" in kana) and 0.5 <= dur <= 4.0
        results.append({"index": i, "slug": slug, "file": file, "category": cat,
                          "text": text, "duration": dur, "kana": kana, "ok": ok})
        print(i, slug, text, dur, "kana_ok:", ok)
    (outdir / "manifest.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ALL OK:", all(r["ok"] for r in results))

if __name__ == "__main__":
    main()
