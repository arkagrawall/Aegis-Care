"""Portal screenshots for the demo film: 1920x1080 CSS px at 2x, plus the boxes of the parts the film points at.
python capture_portal.py   (hub on :8000; writes ../assets/shots/*.png and ../assets/shots/rects.json)"""
import asyncio, base64, json, os, subprocess, tempfile, time, urllib.request
import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
B = "http://localhost:8000"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "shots")
os.makedirs(OUT, exist_ok=True)
demo = json.loads(urllib.request.urlopen(B + "/api/auth/demo").read())
pins = {c["code"]: c["pin"] for c in demo["coordinators"]}
kamla = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kamla.json")))


def login(role, code, pin=None):
    body = {"role": role, "id": code} | ({"secret": pin} if pin else {})
    r = urllib.request.Request(B + "/api/auth/login", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r).read())


def sess(r):
    return {"aegis_token": r["token"], "aegis_role": r["role"], "aegis_code": r["code"], "aegis_name": r.get("name") or ""}


RECTS = {}


async def main():
    prof = tempfile.mkdtemp()
    p = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9334", f"--user-data-dir={prof}", "--hide-scrollbars", "--force-color-profile=srgb", "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9334/json").read()); break
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

            async def ev(expr):
                r = await cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
                return r.get("result", {}).get("value")

            await cmd("Page.enable")
            await cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}, {"name": "prefers-reduced-motion", "value": "reduce"}])

            async def shot(name, url, session=None, js=None, wait=3.0, rects=None, w=1920, h=1080, dsf=2, ready=None):
                await cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=dsf, mobile=w < 768)
                await cmd("Page.navigate", url=B + "/api/health"); await asyncio.sleep(0.4)
                ss = "sessionStorage.clear();localStorage.setItem('aegis_lang','en');" + "".join(f"sessionStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in (session or {}).items())
                await ev(ss)
                await cmd("Page.navigate", url=B + url)
                await asyncio.sleep(wait)
                if ready:
                    for _ in range(60):
                        if await ev(ready): break
                        await asyncio.sleep(0.5)
                    await asyncio.sleep(0.8)
                if js:
                    await ev(js); await asyncio.sleep(1.2)
                r = await cmd("Page.captureScreenshot", format="png")
                open(os.path.join(OUT, name + ".png"), "wb").write(base64.b64decode(r["data"]))
                if rects:
                    RECTS[name] = await ev("(" + json.dumps(rects) + ").reduce((o,[k,s])=>{const e=document.querySelector(s); if(e){const b=e.getBoundingClientRect(); o[k]=[Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]} return o},{})")
                print(name, RECTS.get(name, ""))

            c101 = sess(login("coordinator", "SAM-101", pins["SAM-101"]))
            c102 = sess(login("coordinator", "SAM-102", pins["SAM-102"]))
            ops = sess(login("ops", demo["ops"][0]["code"], demo["ops"][0]["pin"]))
            listed = "!!document.querySelector('.person') && !!document.querySelector('.tl, #detail .tile')"

            await shot("login", "/", wait=2.5, rects=[["form", ".form"], ["story", ".story h2"]])
            await shot("today", "/#/today", c101, ready=listed, rects=[
                ["greet", ".greet"], ["filters", ".filters"], ["urgentGroup", ".grp-h"], ["firstRow", ".person"], ["list", "#qlist"],
                ["detailHead", ".dh"], ["callBtn", "#bCall"], ["next", ".next"], ["nav", ".side .nav"]])
            await shot("reasons", "/#/today", c101, ready=listed, js="document.querySelector('#detail').scrollTop = document.querySelector('.reasons').closest('.ds').offsetTop - 8",
                       rects=[["reasons", ".reasons"], ["r0", ".reasons li:nth-child(1)"], ["r1", ".reasons li:nth-child(2)"], ["r3", ".reasons li:nth-child(4)"]])
            await shot("readings", "/#/today", c101, ready=listed, js="document.querySelector('#detail').scrollTop = document.querySelector('.tiles').closest('.ds').offsetTop - 8",
                       rects=[["tiles", ".tiles"], ["steps", ".tile:nth-child(1)"], ["bp", ".tile:nth-child(4)"], ["source", ".source"]])
            await shot("followup", "/#/today", c101, ready=listed, js="document.querySelector('#bLog').click()",
                       rects=[["dialog", ".dialog"], ["useful", "#fu"], ["save", "#fs"]])
            await shot("sos", "/#/today", c102, ready="!!document.querySelector('.sos-bar') && !!document.querySelector('.person')",
                       rects=[["sosBar", ".sos-bar"], ["sosActs", ".sos-bar .acts"], ["navCount", ".nav .count"]])
            await shot("kamla", f"/#/today/{kamla['senior_id']}", c102, ready="!!document.querySelector('.tl')",
                       js="document.querySelector('details.tx') && (document.querySelector('details.tx').open = true); document.querySelector('#detail').scrollTop = document.querySelector('.tl').closest('.ds').offsetTop - 8",
                       rects=[["activity", ".tl"], ["tx", "details.tx"], ["firstItem", ".tl li"]])
            await shot("people", "/#/people", c101, ready="!!document.querySelector('tbody tr')", rects=[["table", "table.tbl"]])
            await shot("overview", "/#/overview", ops, ready="!!document.querySelector('.kpi .v') && !document.querySelector('.kpi .skel')", wait=4,
                       rects=[["kpis", ".kpis"], ["openAlerts", ".kpis .kpi:nth-child(3)"], ["workload", ".card:nth-of-type(2)"]])
            await shot("overview2", "/#/overview", ops, ready="!!document.querySelector('.grid-3')", wait=2,
                       js="window.scrollTo(0, document.querySelector('.grid-3').getBoundingClientRect().top + scrollY - 90)",
                       rects=[["grid", ".grid-3"], ["falls", ".grid-3 .card:nth-child(2)"], ["calls", ".grid-3 .card:nth-child(3)"]])
            await shot("accuracy", "/#/accuracy", ops, ready="!!document.querySelector('.kpi .v')", wait=2.5,
                       rects=[["kpis", ".kpis"], ["compare", ".card table"], ["combined", "tr:last-child"]])
            await shot("method", "/#/accuracy", ops, ready="!!document.querySelector('details.method')", wait=2.5,
                       js="document.querySelector('details.method').open=true; window.scrollTo(0, document.body.scrollHeight)",
                       rects=[["method", "details.method"]])
            fam = login("family", kamla["family_code"])
            await shot("family", "/family", {"fam_token": fam["token"]}, ready="!!document.querySelector('.hello')", w=430, h=932, dsf=3, wait=2.5)
            await shot("family_login", "/family", None, w=430, h=932, dsf=3, wait=2)
            await shot("today_phone", "/#/today", c101, ready="!!document.querySelector('.person')", w=430, h=932, dsf=3)
            json.dump(RECTS, open(os.path.join(OUT, "rects.json"), "w"), indent=1)
    finally:
        p.terminate()


asyncio.run(main())
