#!/bin/zsh
# usage: t.sh x y [wait]  -> tap then dump source
cd ${0:a:h}
python3 -I wda.py tap $1 $2 >/dev/null
sleep ${3:-4}
python3 -I wda.py source | grep -v "scroll bar" | head -${LINES_MAX:-45}
