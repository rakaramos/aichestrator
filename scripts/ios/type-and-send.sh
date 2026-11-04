#!/bin/zsh
# Types text into a field and taps a button, then prints the screen's text.
# usage: type-and-send.sh "<field label>" "<text>" ["<button label>" (default Send)] [wait seconds (default 25)]
# Needs WDA (WebDriverAgent) on $WDA. Labels are the accessibility labels that `wda.py source` prints.
HERE=${0:a:h}
FIELD=${1:?field label}; TEXT=${2:?text}; BUTTON=${3:-Send}; WAIT=${4:-25}
center() { python3 -I $HERE/wda.py source | grep -F "\"$1\"" | grep -E 'TextView|TextField|Button' | head -1 |
  sed -E 's/.*@\((-?[0-9]+),(-?[0-9]+),([0-9]+),([0-9]+)\).*/\1 \2 \3 \4/' | awk '{print int($1+$3/2), int($2+$4/2)}'; }
F=$(center "$FIELD"); [ -n "$F" ] || { echo "field not found: $FIELD" >&2; exit 1; }
python3 -I $HERE/wda.py tap ${=F} >/dev/null; sleep 2
FREQ=${FREQ:-4} python3 -I $HERE/wda.py type "$TEXT" >/dev/null; sleep 1
B=$(center "$BUTTON"); [ -n "$B" ] || { echo "button not found: $BUTTON" >&2; exit 1; }
python3 -I $HERE/wda.py tap ${=B} >/dev/null
sleep $WAIT
python3 -I $HERE/wda.py source | grep -E 'StaticText|Button' | cut -c1-170 | tail -${LINES_MAX:-14}
