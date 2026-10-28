#!/usr/bin/env bash
# Generate a 4-second silent mp3 used as the standby page's keep-alive loop.
# Usage: bash make_keepalive.sh <out.mp3>
set -euo pipefail
OUT="${1:?usage: make_keepalive.sh <out.mp3>}"
ffmpeg -y -v error -f lavfi -i anullsrc=r=44100:cl=stereo -t 4 "$OUT"
echo "wrote $OUT"
