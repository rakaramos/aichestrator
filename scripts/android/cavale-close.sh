#!/bin/zsh
# close Cavale like a user: Recents, swipe its card away
export ANDROID_SERIAL=${ANDROID_SERIAL:?set ANDROID_SERIAL (see config/devices.local.json)}
adb shell input keyevent KEYCODE_APP_SWITCH; sleep 2
adb shell input swipe 540 1000 540 150 250; sleep 2
adb shell input keyevent KEYCODE_HOME; sleep 1
echo "pid=[$(adb shell pidof co.thefab.parlance.staging)]"
