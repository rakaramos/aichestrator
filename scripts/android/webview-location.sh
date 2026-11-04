#!/bin/zsh
# Prints the location (path and query) of an app's WebView, then saves a screenshot. Use it after a push tap.
# usage: webview-location.sh <package> <screenshot name>   (needs ANDROID_SERIAL; screenshots go to $EV_DIR, default ./ev)
export ANDROID_SERIAL=${ANDROID_SERIAL:?set ANDROID_SERIAL (see config/devices.local.json)}
PKG=${1:?package name}; NAME=${2:?screenshot name}
EV=${EV_DIR:-./ev}; mkdir -p $EV
sleep ${WAIT:-6}
PID=$(adb shell pidof $PKG | tr -d '\r' | awk '{print $1}'); [ -n "$PID" ] || { echo "not running: $PKG" >&2; exit 1; }
P=webview_devtools_remote_$PID
adb forward tcp:9333 localabstract:$P >/dev/null
WS=$(curl -s localhost:9333/json | jq -r '.[] | select(.type=="page") | .webSocketDebuggerUrl' | head -1)
node ${0:a:h:h}/web/cdp-eval.mjs "$WS" 'location.pathname + location.search'
adb forward --remove tcp:9333
adb exec-out screencap -p > $EV/$NAME.png
