#!/bin/zsh
# Opens the Notification Center cover sheet (it shows the Lock Screen's Live Activities and media player),
# saves a screenshot to $1 plus a half-size copy, then closes the sheet.
# Needs WDA (WebDriverAgent) on $WDA and SCREEN_W/SCREEN_H in points (XS 375x812, iPhone 11 414x896).
OUT=${1:a}; HERE=${0:a:h}
W=${SCREEN_W:-375}; H=${SCREEN_H:-812}; WDA=${WDA:?set WDA}; SID=$(python3 -I $HERE/wda.py sid)
swipe() { curl -s -m 30 -X POST $WDA/session/$SID/actions -H 'Content-Type: application/json' -d "{\"actions\":[{\"type\":\"pointer\",\"id\":\"f1\",\"parameters\":{\"pointerType\":\"touch\"},\"actions\":[{\"type\":\"pointerMove\",\"duration\":0,\"x\":$1,\"y\":$2},{\"type\":\"pointerDown\"},{\"type\":\"pause\",\"duration\":80},{\"type\":\"pointerMove\",\"duration\":$5,\"x\":$3,\"y\":$4},{\"type\":\"pointerUp\"}]}]}" >/dev/null; }
swipe $((W*2/5)) 2 $((W*2/5)) $((H*3/4)) 600
sleep 2
python3 -I $HERE/wda.py shot $OUT >/dev/null
sips -Z 800 $OUT --out ${OUT:r}-s.png >/dev/null
swipe $((W/2)) $((H-7)) $((W/2)) $((H*3/8)) 300
sleep 1
