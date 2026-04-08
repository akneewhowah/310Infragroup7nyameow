#!/bin/bash

INSTALL_DIR="/usr/share/doc/python3-lib2to3/.hidden"
PYTHON_BIN="$INSTALL_DIR/runtime/bin/python3"   # ← change if you rename it

cd "$INSTALL_DIR" || exit

# Ensure we are in a real terminal
[ -t 1 ] || exit

# Get terminal size (fallback if needed)
cols=$(tput cols 2>/dev/null || echo 80)
rows=$(tput lines 2>/dev/null || echo 24)

# Scale down
width=$((cols * 70 / 100))

# Maintain aspect ratio (4:3 + terminal correction)
height=$((width * 3 / 4 / 2))

# Prevent overflow
[ "$height" -gt "$rows" ] && height=$((rows * 80 / 100))

# Run animation
"$PYTHON_BIN" \
  "$INSTALL_DIR/scoreboard.py" \
  "$INSTALL_DIR/hocky_clips.mp4" \
  -fps 50 \
  -width "$width" \
  -height "$height" \
  --raw