"""Runs the real first-time setup on the plugged-in phone with the Saathi code from the purchase, taking screenshots.
The phone's own settings are backed up first (prefs_backup_original.xml) and put back with:  python capture_phone.py restore
python capture_phone.py   ->  ../assets/app/*.png"""
import json, os, re, subprocess, sys, time

ADB = r"C:\Users\Arkag\AppData\Local\Android\Sdk\platform-tools\adb.exe"
PKG = "com.aegis.saathi"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "app")
PREFS = "shared_prefs/aegis_senior_prefs.xml"


def adb(*a, binary=False, stdin=None):
    r = subprocess.run([ADB, *a], capture_output=True, input=stdin)
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def nodes():
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    return re.findall(r"<node [^>]*>", adb("shell", "cat", "/sdcard/ui.xml"))


def find(text=None, rid=None, desc=None, contains=None):
    for n in nodes():
        if (text and f'text="{text}"' in n) or (rid and f'resource-id="{PKG}:id/{rid}"' in n) or \
           (desc and f'content-desc="{desc}"' in n) or (contains and contains in n):
            x1, y1, x2, y2 = map(int, re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n).groups())
            return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def tap(p, wait=1.2):
    assert p, "element not found"
    adb("shell", "input", "tap", str(p[0]), str(p[1]))
    time.sleep(wait)


def hide_keyboard():
    if "mInputShown=true" in adb("shell", "dumpsys", "input_method"):
        adb("shell", "input", "keyevent", "KEYCODE_BACK")      # only closes the keyboard
        time.sleep(0.6)


def type_into(rid, text):
    hide_keyboard()
    p = find(rid=rid)
    if not p:                                                   # below the fold: scroll the form up a little
        adb("shell", "input", "swipe", "540", "1500", "540", "900", "300")
        time.sleep(0.6)
        p = find(rid=rid)
    tap(p, 0.6)
    adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    adb("shell", "input", "keyevent", *(["KEYCODE_DEL"] * 30))
    adb("shell", "input", "text", text.replace(" ", "%s"))
    time.sleep(0.6)


def shot(name):
    adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    open(os.path.join(OUT, name + ".png"), "wb").write(adb("exec-out", "screencap", "-p", binary=True))
    print("shot", name)


def write_prefs(xml):
    """Push to /data/local/tmp, then copy into the app's own folder (run-as cannot read our stdin)."""
    tmp = os.path.join(HERE, "_prefs_push.xml")
    open(tmp, "w", encoding="utf-8").write(xml)
    adb("shell", "am", "force-stop", PKG)
    adb("push", tmp, "/data/local/tmp/aegis_prefs.xml")
    adb("shell", "run-as", PKG, "cp", "/data/local/tmp/aegis_prefs.xml", PREFS)
    adb("shell", "rm", "/data/local/tmp/aegis_prefs.xml")
    os.remove(tmp)
    got = adb("shell", "run-as", PKG, "cat", PREFS)
    norm = lambda t: "".join(t.split())
    assert norm(got) == norm(xml), "prefs were not written"


def restore():
    xml = open(os.path.join(HERE, "prefs_backup_original.xml"), encoding="utf-8").read()
    write_prefs(xml)
    adb("shell", "am", "start", "-n", f"{PKG}/.ui.OnboardingActivity")
    print("restored the phone's own settings")


def run():
    os.makedirs(OUT, exist_ok=True)
    orig = open(os.path.join(HERE, "prefs_backup_original.xml"), encoding="utf-8").read()
    keep = {k: re.search(rf'<string name="{k}">([^<]*)</string>', orig) for k in ("server_url", "watch_address", "watch_name")}
    code = json.load(open(os.path.join(HERE, "purchase.json")))["code"]
    fresh = ("<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n<map>\n"
             + "".join(f'    <string name="{k}">{m.group(1)}</string>\n' for k, m in keep.items() if m)
             + '    <string name="lang">en</string>\n    <boolean name="read_aloud" value="true" />\n    <boolean name="haptics" value="true" />\n</map>\n')
    write_prefs(fresh)
    adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    adb("shell", "am", "start", "-n", f"{PKG}/.ui.OnboardingActivity")
    time.sleep(3)
    # welcome slides
    for i in range(1, 7):
        shot(f"slide{i}")
        tap(find(rid="btnNextSlide"), 1.4)
    # setup step 0: language
    time.sleep(1)
    tap(find(rid="tileEn"), 1.0)
    shot("setup_lang")
    tap(find(rid="btnNext"), 1.2)
    # step 1: name and age
    type_into("etSeniorName", "Kamla Devi")
    type_into("etSeniorAge", "72")
    hide_keyboard()
    shot("setup_name")
    tap(find(rid="btnNext"), 1.2)
    # step 2: the Saathi code from the purchase
    type_into("etCoordCode", code)
    type_into("etSeniorCity", "Lucknow")
    hide_keyboard()
    shot("setup_code")
    for rid, val in (("etMyPhone", "9811122334"), ("etEmergencyPhone", "9810012345")):
        p = find(rid=rid)
        if p:
            type_into(rid, val)
    hide_keyboard()
    tap(find(rid="btnNext"), 1.5)
    # step 3: permissions and consent
    shot("setup_perms")
    p = find(rid="cbConsent")
    if p:
        tap(p, 0.6)
    shot("setup_perms2")
    tap(find(rid="btnNext"), 6)
    shot("home_new")
    after_setup()
    restore()


def api(path, body=None, tok=None, dev=None, method=None):
    import urllib.request
    h = {"Content-Type": "application/json"}
    if tok: h["Authorization"] = "Bearer " + tok
    if dev: h["X-Device-Key"] = dev
    r = urllib.request.Request("http://localhost:8000" + path, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    return json.loads(urllib.request.urlopen(r).read())


def after_setup():
    """With Kamla registered: a medicine from her care manager, the real reminder, the home screen moving on, family sharing."""
    prefs = adb("shell", "run-as", PKG, "cat", PREFS)
    sid = re.search(r'<string name="senior_id">([^<]*)</string>', prefs).group(1)
    dev = re.search(r'<string name="device_key">([^<]*)</string>', prefs).group(1)
    demo = api("/api/auth/demo")
    pin = {c["code"]: c["pin"] for c in demo["coordinators"]}["SAM-102"]
    tok = api("/api/auth/login", {"role": "coordinator", "id": "SAM-102", "secret": pin})["token"]
    t1 = time.strftime("%H:%M", time.localtime(time.time() + 150))
    api(f"/api/seniors/{sid}/medicines", {"name": "BP tablet", "dose_text": "Amlodipine 5 mg, after breakfast", "times": [t1, "21:00"]}, tok)
    api(f"/api/seniors/{sid}/contacts", {"name": "Meera Iyer", "relation": "Daughter", "phone": "+91 98100 12345", "is_emergency": True}, tok)
    time.sleep(6)
    shot("home_dose")                                   # the dose is in its window: "Time for your BP tablet"
    # wait for the alarm to ring, over whatever is on screen
    end = time.time() + 200
    while time.time() < end and "DoseReminderActivity" not in adb("shell", "dumpsys", "window").split("mCurrentFocus")[1][:200]:
        time.sleep(3)
    time.sleep(3)
    shot("dose_ring")
    tap(find(rid="btnReminderTaken"), 4)
    shot("home_checkin")                                # dose taken: now "How are you today?"
    p = find(rid="optFine")
    if p:
        tap(p, 4.5)
    shot("home_next")                                   # next medicine at 9 PM, with a countdown
    fam = api("/api/senior/family-consent", {"consent": True}, dev=dev)       # Kamla agrees to share a weekly summary
    json.dump({"senior_id": sid, "device_key": dev, "coordinator": "SAM-102", "family": fam}, open(os.path.join(HERE, "kamla_new.json"), "w"))
    print("kamla", sid)


if __name__ == "__main__":
    restore() if sys.argv[1:] == ["restore"] else run()
