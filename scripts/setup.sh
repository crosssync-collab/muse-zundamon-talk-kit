#!/usr/bin/env bash
# Install and start the VOICEVOX engine (0.26.0, Linux CPU x64).
# Usage: bash setup.sh <install_parent_dir>   e.g. bash setup.sh ~/workspace/voicevox
set -euo pipefail
PARENT="${1:?usage: setup.sh <install_parent_dir>}"
PKG="voicevox_engine-linux-cpu-x64-0.26.0.7z.001"
URL="https://github.com/VOICEVOX/voicevox_engine/releases/download/0.26.0/$PKG"
EXPECTED_SIZE=1848012250
mkdir -p "$PARENT"
cd "$PARENT"
if [ ! -f "$PKG" ]; then
  echo "downloading engine package (~1.85GB)..."
  curl -L -o "$PKG" "$URL"
fi
SIZE=$(stat -c %s "$PKG")
if [ "$SIZE" != "$EXPECTED_SIZE" ]; then
  echo "ERROR: unexpected package size: $SIZE (expected $EXPECTED_SIZE)" >&2
  exit 1
fi
if [ ! -d linux-cpu-x64 ]; then
  mkdir -p linux-cpu-x64
  7z x -olinux-cpu-x64 "$PKG" > /dev/null
fi
cd linux-cpu-x64
if ! curl -s -m 3 http://127.0.0.1:50021/version > /dev/null; then
  nohup ./run --host 127.0.0.1 --port 50021 > engine.log 2>&1 &
  for i in $(seq 1 30); do
    sleep 2
    if curl -s -m 3 http://127.0.0.1:50021/version > /dev/null; then break; fi
  done
fi
echo "version: $(curl -s http://127.0.0.1:50021/version)"
curl -s http://127.0.0.1:50021/speakers | grep -q "ずんだもん" && echo "speaker check: ずんだもん found (normal = style id 3)"
echo "engine ready at http://127.0.0.1:50021"
