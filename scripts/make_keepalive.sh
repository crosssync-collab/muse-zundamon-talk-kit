#!/usr/bin/env bash
# Generate the keep-alive loop mp3 for the standby page.
#
# The loop must NOT be digital silence and must not be very short:
# Chrome does not treat sub-~5-second or fully silent media as
# "playing", so such a loop earns no media presence in the
# background. This generates 30 seconds of pink noise at about
# -60 dB (inaudible in practice, but real, non-zero audio samples)
# encoded as a 64 kbps mp3.
#
# Usage: bash make_keepalive.sh <out.mp3>
set -euo pipefail
OUT="${1:?usage: make_keepalive.sh <out.mp3>}"
ffmpeg -y -v error -f lavfi -i "anoisesrc=color=pink:sample_rate=44100:duration=30" \
  -af "volume=-60dB" -codec:a libmp3lame -b:a 64k "$OUT"
echo "wrote $OUT"
