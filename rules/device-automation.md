# Device automation

What works on the test phones, and what needs a person. Read this before you say "needs Rafael".

## iPhone (WebDriverAgent)

- Build WebDriverAgent once for each phone. Run it with `xcodebuild test-without-building` (team `DPE4LURAUZ`, bundle `co.thefab.qa.WebDriverAgentRunner`).
- Forward one local port for each phone: `pymobiledevice3 usbmux forward --serial <udid> <port> 8100`. Ports are in `config/devices.local.json` (copy of `config/devices.example.json`, not committed).
- Drive the phone with `scripts/ios/wda.py` (`WDA=http://127.0.0.1:<port>`). Read `source` before each tap: coordinates differ for each screen size.
- To see the Lock Screen, Live Activities and the media player, run `scripts/ios/cover-sheet-shot.sh`. WebDriverAgent cannot lock the phone, and a locked screen with a passcode cannot be captured.
- To see what the Lock Screen gets, send the app to the background (`wda.py home`) instead of locking the phone.
- System banners (AlarmKit, CallKit) ignore WebDriverAgent taps. A person must tap Stop or Answer.
- Install Firebase builds: get the download URL from fab-mcp `firebase_app_distribution` `get_download_url`, unzip, then `xcrun devicectl device install app`.
- WebDriverAgent can block StandBy. Stop it before a StandBy check.

## iPhone, web views

- Capacitor apps with an inspectable web view: `pymobiledevice3 webinspector js-shell --bundle-id <id>`.
- Some staging builds turn inspection off. Then use screenshots only.

## Android (adb)

- `scripts/android/ui-dump.sh [pattern]` prints the text and tap points on screen.
- The WebView debugger is at `adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>`. Then use `scripts/web/cdp-eval.mjs`.
- To get the Firebase ID token for a staging API call, read it from the WebView heap with `scripts/web/cdp-heap-firebase-token.mjs`. Keep the token in a file with mode 600 and never print it.
- A force-stopped app gets no push. To close an app as a person does, swipe it out of Recents (`scripts/android/close-app.sh <package>`).

## Always a person

- Entering a device passcode, unlocking with Face ID, and pressing the side button.
- Listening to sound, flipping the silent switch, and speaking in a voice call.
- Changing the device clock or security settings.

## No app-specific code

- Scripts in this repo work for any app. Take the app's package or bundle ID, labels and coordinates as arguments or environment variables.
- Never put an app's name, bundle ID, screen labels or flow in a script, rule or prompt. Keep app-specific steps in the session's scratch folder, and delete them when the request is done.
