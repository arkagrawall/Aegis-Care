"""Care portal and family page at 1920x1080 for the film: Rajesh Verma's list, a person's record with charts,
Kamla's medicines, the operations overview and Kamla's family page.  python capture_portal.py"""
import asyncio, base64, json, os, subprocess, tempfile, time, urllib.request
import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "..", "assets", "shots")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
B = "http://localhost:8000"
K = json.load(open(os.path.join(HERE, "kamla_new.json")))


def req(path, body=None, tok=None):
    h = {"Content-Type": "application/json"}
    if tok: h["Authorization"] = "Bearer " + tok
    r = urllib.request.Request(B + path, data=json.dumps(body).encode() if body is not None else None, headers=h)
    return json.loads(urllib.request.urlopen(r).read())


async def main():
    demo = req("/api/auth/demo")
    pin = {c["code"]: c["pin"] for c in demo["coordinators"]}
    c = req("/api/auth/login", {"role": "coordinator", "id": "SAM-102", "secret": pin["SAM-102"]})
    o = req("/api/auth/login", {"role": "ops", "id": demo["ops"][0]["code"], "secret": demo["ops"][0]["pin"]})
    q = req("/api/coordinator/SAM-102/seniors", tok=c["token"])["seniors"]
    top = q[0]["senior_id"]
    fam_code = K["family"].get("family_code") or K["family"].get("code")
    f = req("/api/auth/login", {"role": "family", "id": fam_code})
    cs = {"aegis_token": c["token"], "aegis_role": c["role"], "aegis_code": c["code"], "aegis_name": c.get("name") or ""}
    os_ = {"aegis_token": o["token"], "aegis_role": o["role"], "aegis_code": o["code"], "aegis_name": o.get("name") or ""}

    prof = tempfile.mkdtemp()
    p = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9341", f"--user-data-dir={prof}", "--hide-scrollbars", "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9341/json").read()); break
            except Exception:
                time.sleep(0.2)
        ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url, max_size=None) as ws:
            n = 0
            async def cmd(method, **params):
                nonlocal n
                n += 1; my = n
                await ws.send(json.dumps({"id": my, "method": method, "params": params}))
                while True:
                    m = json.loads(await ws.recv())
                    if m.get("id") == my:
                        return m.get("result", m)

            async def js(expr):
                return (await cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)).get("result", {}).get("value")

            async def page(url, session, wait=8, w=1920, h=1080):
                await cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
                await cmd("Page.navigate", url=B + "/api/health")
                await asyncio.sleep(0.5)
                await js("sessionStorage.clear();" + "".join(f"sessionStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in session.items()) + "true")
                await cmd("Page.navigate", url=B + url)
                await asyncio.sleep(wait)

            async def shot(name):
                r = await cmd("Page.captureScreenshot", format="png")
                open(os.path.join(SHOTS, name + ".png"), "wb").write(base64.b64decode(r["data"]))
                print("shot", name)

            await cmd("Page.enable")
            await cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])
            await page(f"/portal#/today/{top}", cs)
            await shot("portal_today")
            await js("document.querySelector('#vitFig').scrollIntoView({block: 'center'}); true")
            await asyncio.sleep(1)
            await shot("portal_vitals")
            await page(f"/portal#/today/{K['senior_id']}", cs)
            await js("[...document.querySelectorAll('.ds .overline')].find(e => /Medicines/.test(e.textContent)).scrollIntoView({block: 'start'}); true")
            await asyncio.sleep(1)
            await shot("portal_kamla_meds")
            await page("/portal#/overview", os_, wait=12)
            await shot("portal_overview")
            await page("/family", {"fam_token": f["token"]}, wait=5, w=430, h=932)
            await shot("family_home")
            await js("window.scrollTo(0, 560); true")
            await asyncio.sleep(1)
            await shot("family_home2")
    finally:
        p.terminate()

asyncio.run(main())
