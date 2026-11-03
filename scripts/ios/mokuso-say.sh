#!/bin/zsh
cd ${0:a:h}
Y=$(python3 -I wda.py source | grep 'TextView "Message Mira"' | sed -E 's/.*@\([0-9]+,([0-9]+),.*/\1/')
python3 -I wda.py tap 120 $((Y+20)) >/dev/null; sleep 2
FREQ=4 python3 -I wda.py type "$1" >/dev/null; sleep 1
B=$(python3 -I wda.py source | grep 'Button "Send"' | sed -E 's/.*@\(([0-9]+),([0-9]+),.*/\1 \2/')
python3 -I wda.py tap $(echo $B | awk '{print $1+23, $2+23}') >/dev/null
sleep ${2:-25}
python3 -I wda.py source | grep -E 'StaticText|Button' | grep -v -E 'Key|"(Chat|Plan|Powers)"' | cut -c1-170 | tail -14
