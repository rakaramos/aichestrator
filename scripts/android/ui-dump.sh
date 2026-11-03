#!/bin/zsh
# dump Android UI: text/desc with center coords. usage: ui.sh [grep-pattern]
export ANDROID_SERIAL=${ANDROID_SERIAL:?set ANDROID_SERIAL (see config/devices.local.json)}
adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
adb exec-out cat /sdcard/ui.xml | python3 -I -c '
import sys,re
x=sys.stdin.read()
for m in re.finditer(r"<node [^>]*?text=\"([^\"]*)\"[^>]*?content-desc=\"([^\"]*)\"[^>]*?bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"",x):
    t,d,a,b,c,e=m.groups()
    if t or d: print(f"{(int(a)+int(c))//2},{(int(b)+int(e))//2}\t{t}\t{d}")
' | grep -i -E "${1:-.}"
