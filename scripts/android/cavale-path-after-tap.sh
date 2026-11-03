#!/bin/zsh
# print Cavale WebView location after a push tap; arg: screenshot name
export ANDROID_SERIAL=${ANDROID_SERIAL:?set ANDROID_SERIAL (see config/devices.local.json)}
EV=${EV_DIR:-./ev}; mkdir -p $EV
sleep 6
P=$(adb shell cat /proc/net/unix | grep -o "webview_devtools_remote_[0-9]*" | sort -u | tail -1)
adb forward tcp:9333 localabstract:$P >/dev/null
WS=$(curl -s localhost:9333/json | jq -r '.[] | select(.type=="page") | .webSocketDebuggerUrl' | head -1)
node ${0:a:h:h}/web/cdp-eval.mjs "$WS" 'location.pathname + location.search'
adb forward --remove tcp:9333
adb exec-out screencap -p > $EV/$1.png
