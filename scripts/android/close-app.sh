#!/bin/zsh
# Closes an app as a person does: Recents, then swipe its card away. A force stop is not the same: the app then gets no push.
# usage: close-app.sh <package>   (needs ANDROID_SERIAL; see config/devices.local.json)
export ANDROID_SERIAL=${ANDROID_SERIAL:?set ANDROID_SERIAL (see config/devices.local.json)}
PKG=${1:?package name}
read W H <<< "$(adb shell wm size | grep -o '[0-9]*x[0-9]*' | tail -1 | tr x ' ')"
# Bring the app to the front first, so its card is the centred one in Recents.
adb shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 3
adb shell input keyevent KEYCODE_APP_SWITCH; sleep 2
adb shell input swipe $((W/2)) $((H*43/100)) $((W/2)) $((H/16)) 250; sleep 2
adb shell input keyevent KEYCODE_HOME; sleep 1
echo "pid=[$(adb shell pidof $PKG)]"
