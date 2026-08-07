#!/bin/bash
# Linear stringout: ffmpeg concat with audio, no crossfades, no smoothing.
# Usage: ./stringout.sh shot_01.mp4 shot_02.mp4 ... output.mp4
#
# All input clips must have:
#   - Same resolution (e.g., 720x1280)
#   - Same frame rate
#   - Both video + audio streams
#
# Output is a single mp4 with hard cuts and original audio preserved per clip.
# This is the deliverable the operator opens in FCP for editing.

set -e

if [ $# -lt 3 ]; then
  echo "Usage: $0 <input1.mp4> <input2.mp4> ... <output.mp4>"
  echo "Need at least 2 inputs and 1 output."
  exit 1
fi

OUTPUT="${@: -1}"
INPUTS=("${@:1:$#-1}")
N="${#INPUTS[@]}"

# Verify all inputs exist
for f in "${INPUTS[@]}"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: input file not found: $f"
    exit 2
  fi
done

# Verify all inputs have audio
for f in "${INPUTS[@]}"; do
  if ! ffprobe -v error -select_streams a -show_entries stream=codec_type -of default=noprint_wrappers=1:nokey=1 "$f" | grep -q audio; then
    echo "WARNING: $f has no audio stream — concat may fail."
  fi
done

# Build the input args + filter expression
INPUT_ARGS=""
FILTER=""
for i in $(seq 0 $((N-1))); do
  INPUT_ARGS+=" -i \"${INPUTS[$i]}\""
  FILTER+="[${i}:v][${i}:a]"
done
FILTER+="concat=n=${N}:v=1:a=1[v][a]"

# Run ffmpeg
echo "Concatenating $N clips → $OUTPUT"
echo "Filter: $FILTER"
echo ""

eval "ffmpeg -y $INPUT_ARGS \
  -filter_complex \"$FILTER\" \
  -map \"[v]\" -map \"[a]\" \
  -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  \"$OUTPUT\""

echo ""
echo "Done. Verifying output..."
ffprobe -v error -show_entries stream=codec_type,duration:format=duration,size -of default=noprint_wrappers=1 "$OUTPUT"
