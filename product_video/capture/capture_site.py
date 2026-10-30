"""Captures the Samarth Saathi website and the buy flow at 1920x1080 with headless Chrome (CDP).
The real Razorpay checkout is captured as it opens; for the success screen the checkout script is replaced by a
stand-in that signs a demo payment with the TEST secret, so the hub's real verification issues a real Saathi code.
python capture_site.py   ->  ../assets/shots/*.png and purchase.json (the code, for the phone capture)"""
import asyncio, base64, json, os, re, subprocess, tempfile, time, urllib.request
import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "..", "assets", "shots")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
B = "http://localhost:8000"
ENV = open(os.path.join(HERE, "..", "..", "coordinator_hub", ".env"), encoding="utf-8").read()
SECRET = re.search(r"^RAZORPAY_KEY_SECRET=(.*)$", ENV, re.M).group(1).strip()

FAKE = """window.Razorpay = function (o) { this.o = o; };
Razorpay.prototype.on = function () {};
Razorpay.prototype.open = async function () {
  const o = this.o, pid = "pay_DEMOVIDEO" + o.order_id.slice(-6);
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode(%s), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const s = await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(o.order_id + "|" + pid));
  const hex = [...new Uint8Array(s)].map((b) => b.toString(16).padStart(2, "0")).join("");
  setTimeout(() => o.handler({ razorpay_order_id: o.order_id, razorpay_payment_id: pid, razorpay_signature: hex }), 200);
};""" % json.dumps(SECRET)

FILL = """(() => { const f = document.querySelector('#f'); const v = { elder_name: 'Kamla Devi', elder_city: 'Lucknow', name: 'Meera Iyer', email: 'meera.iyer@example.com', phone: '+91 98100 12345' };
  for (const [k, x] of Object.entries(v)) { f.elements[k].value = x; f.elements[k].dispatchEvent(new Event('input', { bubbles: true })); } return true; })()"""


async def main():
    os.makedirs(SHOTS, exist_ok=True)
    prof = tempfile.mkdtemp()
    p = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9340", f"--user-data-dir={prof}", "--hide-scrollbars", "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9340/json").read()); break
            except Exception:
                time.sleep(0.2)
        ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url, max_size=None) as ws:
            n, fake = 0, {"on": False}

            async def handle(m):
                if m.get("method") == "Fetch.requestPaused":
                    rid = m["params"]["requestId"]
                    url = m["params"]["request"]["url"]
                    if fake["on"] and "checkout.razorpay.com" in url:
                        await ws.send(json.dumps({"id": 900000 + int(time.time() * 1000) % 99999, "method": "Fetch.fulfillRequest", "params": {
                            "requestId": rid, "responseCode": 200, "responseHeaders": [{"name": "Content-Type", "value": "application/javascript"}],
                            "body": base64.b64encode(FAKE.encode()).decode()}}))
                    else:
                        await ws.send(json.dumps({"id": 800000 + int(time.time() * 1000) % 99999, "method": "Fetch.continueRequest", "params": {"requestId": rid}}))

            async def cmd(method, **params):
                nonlocal n
                n += 1; my = n
                await ws.send(json.dumps({"id": my, "method": method, "params": params}))
                while True:
                    m = json.loads(await ws.recv())
                    await handle(m)
                    if m.get("id") == my:
                        return m.get("result", m)

            async def wait(sec):
                end = time.time() + sec
                while time.time() < end:          # keep answering intercepted requests while waiting
                    try:
                        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=max(0.05, end - time.time())))
                        await handle(m)
                    except asyncio.TimeoutError:
                        pass

            async def js(expr):
                r = await cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
                return r.get("result", {}).get("value")

            async def shot(name):
                r = await cmd("Page.captureScreenshot", format="png")
                open(os.path.join(SHOTS, name + ".png"), "wb").write(base64.b64decode(r["data"]))
                print("shot", name)

            async def go(url, w=1920, h=1080, settle=3):
                await cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
                await cmd("Page.navigate", url=B + url)
                await wait(settle)

            await cmd("Page.enable")
            await cmd("Fetch.enable", patterns=[{"urlPattern": "*checkout.razorpay.com*"}])

            # website
            await go("/")
            await shot("site_hero")
            for sec, name in (("#saathi", "site_saathi"), (".feat", "site_features"), (".steps3", "site_steps"), ("#plans", "site_plans")):
                await js(f"document.querySelector('{sec}').scrollIntoView({{block: 'start'}}); window.scrollBy(0, -96); true")
                await wait(0.8)
                await shot(name)

            # buy page: filled in
            await go("/subscribe?plan=yearly")
            await js(FILL)
            await wait(0.5)
            await shot("buy_form")
            await js("window.scrollTo(0, 420); true")
            await wait(0.5)
            await shot("buy_form2")

            # the real Razorpay checkout as it opens (test mode)
            await js("window.scrollTo(0, 0); document.querySelector('#pay').click(); true")
            await wait(9)
            await shot("buy_checkout")

            # success: the stand-in checkout signs a demo payment; the hub verifies it and issues the code
            fake["on"] = True
            await go("/subscribe?plan=yearly")
            await js(FILL)
            await js("document.querySelector('#pay').click(); true")
            await wait(5)
            await js("window.scrollTo(0, 0); true")
            await shot("buy_success")
            code = await js("(document.querySelector('#code') || {}).textContent || ''")
            await js("document.querySelector('.cm').scrollIntoView({block: 'center'}); true")
            await wait(0.5)
            await shot("buy_success2")
            print("code", code)
            json.dump({"code": code}, open(os.path.join(HERE, "purchase.json"), "w"))
    finally:
        p.terminate()

asyncio.run(main())
