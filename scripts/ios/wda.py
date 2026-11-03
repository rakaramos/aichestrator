#!/usr/bin/env python3
"""Tiny WebDriverAgent CLI for the USB-forwarded iPhone (127.0.0.1:8100)."""
import base64, json, os, sys, urllib.request

BASE = os.environ["WDA"]  # e.g. http://127.0.0.1:8101 (one port per phone, see config/devices.local.json)
SID_FILE = os.path.join(os.path.dirname(__file__), ".sid-" + BASE.rsplit(":", 1)[1])


def req(method, path, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def sid():
    if os.path.exists(SID_FILE):
        s = open(SID_FILE).read().strip()
        if req("GET", f"/session/{s}").get("value") is not None and "error" not in str(req("GET", f"/session/{s}"))[:200]:
            return s
    r = req("POST", "/session", {"capabilities": {"alwaysMatch": {
        "shouldWaitForQuiescence": False, "waitForIdleTimeout": 0}}})
    s = r["sessionId"]
    open(SID_FILE, "w").write(s)
    req("POST", f"/session/{s}/appium/settings", {"settings": {
        "waitForIdleTimeout": 0, "animationCoolOffTimeout": 0, "snapshotMaxDepth": 60}})
    return s


def walk(node, out, depth=0):
    label = node.get("label") or node.get("name") or ""
    value = node.get("value") or ""
    r = node.get("rect") or {}
    if (label or value) and node.get("isVisible", "1") in ("1", True, None):
        out.append(f'{"  "*min(depth,8)}{node.get("type")} "{label}"'
                   + (f' value="{value}"' if value and value != label else "")
                   + f' @({r.get("x")},{r.get("y")},{r.get("width")},{r.get("height")})')
    for c in node.get("children") or []:
        walk(c, out, depth + 1)


def find(s, using, value):
    r = req("POST", f"/session/{s}/elements", {"using": using, "value": value})
    return r.get("value") or []


def main(argv):
    cmd, args = argv[0], argv[1:]
    if cmd == "sid":
        print(sid())
    elif cmd == "activate":
        print(req("POST", f"/session/{sid()}/wda/apps/activate", {"bundleId": args[0]}))
    elif cmd == "terminate":
        print(req("POST", f"/session/{sid()}/wda/apps/terminate", {"bundleId": args[0]}))
    elif cmd == "state":
        print(req("POST", f"/session/{sid()}/wda/apps/state", {"bundleId": args[0]}))
    elif cmd == "source":
        out = []
        walk(req("GET", f"/session/{sid()}/source?format=json", timeout=120)["value"], out)
        print("\n".join(out))
    elif cmd == "rawsource":
        print(json.dumps(req("GET", f"/session/{sid()}/source?format=json", timeout=120)["value"])[:200000])
    elif cmd == "shot":
        png = base64.b64decode(req("GET", "/screenshot")["value"])
        open(args[0], "wb").write(png)
        print(args[0])
    elif cmd == "tap":
        x, y = float(args[0]), float(args[1])
        print(req("POST", f"/session/{sid()}/wda/tap", {"x": x, "y": y}))
    elif cmd == "hold":
        x, y, d = float(args[0]), float(args[1]), float(args[2]) if len(args) > 2 else 1.5
        print(req("POST", f"/session/{sid()}/wda/touchAndHold", {"x": x, "y": y, "duration": d}))
    elif cmd == "swipe":
        x1, y1, x2, y2 = map(float, args[:4])
        d = float(args[4]) if len(args) > 4 else 0.3
        print(req("POST", f"/session/{sid()}/wda/dragfromtoforduration",
                  {"fromX": x1, "fromY": y1, "toX": x2, "toY": y2, "duration": d}))
    elif cmd in ("click", "clickp", "exists", "existsp"):
        # click "<label>" (accessibility id) or clickp "<NSPredicate>"
        s = sid()
        using = "predicate string" if cmd.endswith("p") else "accessibility id"
        els = find(s, using, args[0])
        if cmd.startswith("exists"):
            print(len(els))
            return
        if not els:
            print("NOT FOUND", args[0]); sys.exit(1)
        idx = int(args[1]) if len(args) > 1 else 0
        eid = els[idx]["ELEMENT"]
        print(req("POST", f"/session/{s}/element/{eid}/click"))
    elif cmd == "type":
        print(req("POST", f"/session/{sid()}/wda/keys", {"value": list(args[0]), "frequency": int(os.environ.get("FREQ", "6"))}))
    elif cmd == "home":
        print(req("POST", "/wda/homescreen"))
    elif cmd == "size":
        print(req("GET", f"/session/{sid()}/window/size"))
    else:
        print("unknown", cmd); sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
