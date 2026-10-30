"""Builds the HyperFrames composition from the narration timings and the captured screens.
python build.py  ->  ../index.html, ../compositions/*.html
Every scene is timed to its own voice clip: highlights land on the word that names them."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
WORDS = {s["id"]: s for s in json.load(open(os.path.join(ROOT, "assets", "voice", "words.json"), encoding="utf-8"))}
SCRIPT = {s["id"]: s["text"] for s in json.load(open(os.path.join(HERE, "script.json"), encoding="utf-8"))}
RECTS = json.load(open(os.path.join(ROOT, "assets", "shots", "rects.json")))
W, H = 1920, 1080
LEAD = {"s01": 1.4}
TAIL = {"s16": 3.4}
MUSIC = os.path.exists(os.path.join(ROOT, "assets", "music", "bed.mp3"))

# palette
TEAL, DEEP, NIGHT, CANVAS, INK, ACCENT = "#0d7a69", "#084c42", "#0a2a26", "#f4f6f5", "#14211f", "#f5b03c"

FONT = """@font-face { font-family: "Mukta"; src: url("assets/fonts/mukta_regular.ttf") format("truetype"); font-weight: 400; }
@font-face { font-family: "Mukta"; src: url("assets/fonts/mukta_semibold.ttf") format("truetype"); font-weight: 600; }
@font-face { font-family: "Mukta"; src: url("assets/fonts/mukta_bold.ttf") format("truetype"); font-weight: 700; }"""

ICON = {
    "logo": '<path d="M12,2.8l8,3.1v6c0,4.9 -3.4,8.5 -8,10.3C7.4,20.4 4,16.8 4,11.9v-6z"/><path d="M7.8,12.4h2.2l1.3,-2.6 2,5 1.3,-2.4h1.6"/>',
    "steps": '<path d="M8.2,3.5C9.9,3.5 10.8,5.3 10.5,7.4 10.2,9.5 9.2,10.5 8,10.5 6.8,10.5 6,9.4 6,7.6 6,5.2 6.8,3.5 8.2,3.5z"/><path d="M16.2,9.5C17.9,9.5 18.8,11.3 18.5,13.4 18.2,15.5 17.2,16.5 16,16.5 14.8,16.5 14,15.4 14,13.6 14,11.2 14.8,9.5 16.2,9.5z"/>',
    "moon": '<path d="M19,14.5A7.5,7.5 0 1 1 9.5,5 6,6 0 0 0 19,14.5z"/>',
    "pill": '<g transform="rotate(-45 12 12)"><path d="M8,8.2H16A3.8,3.8 0 0 1 16,15.8H8A3.8,3.8 0 0 1 8,8.2z"/><path d="M12,8.2V15.8"/></g>',
    "check": '<path d="M5.2,12.6l4.4,4.4L18.8,7.6"/>',
    "warn": '<path d="M12,3.6L21,19.4H3z"/><path d="M12,9.8v4.4"/><path d="M12,17h.01"/>',
    "fall": '<circle cx="15" cy="5.5" r="2"/><path d="M13.5,9L9,12.5l3,3-1.5,5"/><path d="M9,12.5L5,11"/><path d="M15,10.5l3,3"/><path d="M4,20.5h16"/>',
    "pause": '<circle cx="12" cy="12" r="9"/><path d="M10,9v6"/><path d="M14,9v6"/>',
    "phone": '<path d="M6.2,3.8h3l1.5,3.9-1.9,1.4a11,11 0 0 0 4.1,4.1l1.4,-1.9 3.9,1.5v3A2.2,2.2 0 0 1 15.9,19.9C9.2,19.3 4.7,14.8 4.1,8.1A2.2,2.2 0 0 1 6.2,3.8z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12,7.4V12l3.2,1.9"/>',
    "user": '<circle cx="12" cy="7.5" r="3.8"/><path d="M4.6,20.4C5.2,16.8 8.2,14.8 12,14.8S18.8,16.8 19.4,20.4"/>',
    "users": '<circle cx="9" cy="8" r="3.4"/><path d="M2.8,19.5C3.4,16.3 5.9,14.5 9,14.5S14.6,16.3 15.2,19.5"/><path d="M15.5,4.9a3.4,3.4 0 0 1 0,6.2"/><path d="M17.5,14.8c2,.6 3.4,2.2 3.8,4.7"/>',
    "heart": '<path d="M12,19.6C5.5,14.3 3.2,11.5 3.2,8.5A4.6,4.6 0 0 1 12,6.7A4.6,4.6 0 0 1 20.8,8.5C20.8,11.5 18.5,14.3 12,19.6z"/>',
    "shield": '<path d="M12,3l7.2,2.8v5.6c0,4.6 -3.1,8 -7.2,9.6C7.9,19.4 4.8,16 4.8,11.4V5.8z"/><path d="M8.8,12l2.4,2.4L15.6,9.6"/>',
    "bulb": '<path d="M9,17.5h6"/><path d="M10,20.5h4"/><path d="M12,3.5a6,6 0 0 0 -3.6,10.8c.7,.6 1.1,1.4 1.1,2.2h5c0,-.8 .4,-1.6 1.1,-2.2A6,6 0 0 0 12,3.5z"/>',
}


def ico(n, size=28, color="currentColor", sw=1.8):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICON[n]}</svg>'


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def dur(sid):
    return round(LEAD.get(sid, 0.6) + WORDS[sid]["duration"] + TAIL.get(sid, 0.7), 2)


def at(sid, phrase, nth=0, end=False):
    """Scene-local time of the first word of `phrase` (or the end of its last word)."""
    ws, parts = WORDS[sid]["words"], [norm(p) for p in phrase.split()]
    hits = 0
    for i in range(len(ws)):
        if all(i + k < len(ws) and norm(ws[i + k]["text"]).startswith(parts[k]) for k in range(len(parts))):
            if hits == nth:
                w = ws[i + len(parts) - 1] if end else ws[i]
                return round(LEAD.get(sid, 0.6) + (w["end"] if end else w["start"]), 2)
            hits += 1
    raise KeyError(f"{sid}: '{phrase}' not in narration")


def scene_file(sid, css, html, js, d):
    return f"""<template>
  <style>
    {FONT}
    #root {{ position: absolute; inset: 0; overflow: hidden; font-family: "Mukta", sans-serif; color: #fff; }}
    #root * {{ box-sizing: border-box; }}
    #{sid}-wrap {{ position: absolute; inset: 0; }}
    .bg {{ position: absolute; inset: 0; background: radial-gradient(120% 90% at 20% 0%, #10594f 0%, {NIGHT} 55%, #061b18 100%); }}
    .frame {{ position: absolute; overflow: hidden; border-radius: 18px; background: {CANVAS}; box-shadow: 0 30px 80px rgba(0,0,0,.45), 0 0 0 1px rgba(255,255,255,.08); }}
    .bar {{ position: absolute; left: 0; right: 0; top: 0; height: 34px; background: #e9eeec; display: flex; align-items: center; gap: 8px; padding-left: 16px; z-index: 3; }}
    .bar i {{ width: 11px; height: 11px; border-radius: 50%; background: #c9d2ce; }}
    .bar b {{ margin-left: 18px; font: 600 15px "Mukta"; color: #5f6e69; }}
    .view {{ position: absolute; left: 0; right: 0; bottom: 0; overflow: hidden; }}
    .cam {{ position: absolute; left: 0; top: 0; transform-origin: 0 0; }}
    .cam img {{ display: block; }}
    .spot {{ position: absolute; border-radius: 12px; border: 3px solid {ACCENT}; box-shadow: 0 0 0 4000px rgba(4,22,19,.42), 0 0 24px rgba(245,176,60,.55); opacity: 0; }}
    .chip {{ position: absolute; display: inline-flex; align-items: center; gap: 12px; padding: 10px 22px 10px 16px; border-radius: 999px; background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.18); font: 600 26px "Mukta"; color: #fff; }}
    .kicker {{ font: 700 28px "Mukta"; letter-spacing: .14em; text-transform: uppercase; color: #8fd9c9; }}
    .phone {{ position: absolute; border-radius: 52px; background: #0b0f0e; padding: 13px; box-shadow: 0 30px 70px rgba(0,0,0,.5), 0 0 0 2px rgba(255,255,255,.08); }}
    .phone .scr {{ position: relative; width: 100%; height: 100%; border-radius: 40px; overflow: hidden; background: #fff; }}
    .phone .scr img {{ position: absolute; left: 0; top: 0; width: 100%; }}
    .pt {{ display: flex; align-items: flex-start; gap: 18px; font: 600 38px/1.25 "Mukta"; color: #fff; }}
    .pt .ic {{ flex: none; width: 56px; height: 56px; border-radius: 16px; display: grid; place-items: center; background: rgba(143,217,201,.14); color: #8fd9c9; }}
    .pt small {{ display: block; font: 400 28px/1.35 "Mukta"; color: #b9d6cf; margin-top: 4px; }}
    {css}
  </style>
  <div id="root" data-composition-id="{sid}" data-width="{W}" data-height="{H}">
    <div id="{sid}-wrap"><div class="bg"></div>{html}</div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {"" if sid == "s01" else f'tl.fromTo("#{sid}-wrap", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.45, ease: "power2.out" }}, 0);'}
    {js}
    tl.to("#{sid}-wrap", {{ opacity: 0, duration: 0.35, ease: "power2.in" }}, {d - 0.42:.2f});
    window.__timelines["{sid}"] = tl;
  </script>
</template>
"""


# ------------------------------------------------------------------ building blocks
class Screen:
    """A browser frame showing a 1920x1080 portal capture, with a camera that pushes in on named boxes."""

    def __init__(self, sid, img, label, x=210, y=40, w=1500):
        self.sid, self.img, self.label, self.x, self.y, self.w = sid, img, label, x, y, w
        self.vh = round(w * 1080 / 1920)
        self.k = w / 1920
        self.js, self.spots, self.n = [], [], 0
        self.cam = f"#{sid}-cam"

    def rect(self, r):
        return [v * self.k for v in r]

    def zoom(self, t, r, s, d=1.1):
        x, y, w, h = self.rect(r)
        cx, cy = x + w / 2, y + h / 2
        tx = min(0, max(self.w - s * self.w, self.w / 2 - s * cx))
        ty = min(0, max(self.vh - s * self.vh, self.vh / 2 - s * cy))
        self.js.append(f'tl.to("{self.cam}", {{ x: {tx:.1f}, y: {ty:.1f}, scale: {s}, duration: {d}, ease: "power2.inOut" }}, {t:.2f});')

    def reset(self, t, d=1.0):
        self.js.append(f'tl.to("{self.cam}", {{ x: 0, y: 0, scale: 1, duration: {d}, ease: "power2.inOut" }}, {t:.2f});')

    def spot(self, t, r, until, pad=8):
        x, y, w, h = self.rect(r)
        self.n += 1
        sid = f"{self.sid}-sp{self.n}"
        self.spots.append(f'<div class="spot" id="{sid}" style="left:{x - pad:.0f}px;top:{y - pad:.0f}px;width:{w + 2 * pad:.0f}px;height:{h + 2 * pad:.0f}px"></div>')
        self.js.append(f'tl.fromTo("#{sid}", {{ opacity: 0, scale: 1.04 }}, {{ opacity: 1, scale: 1, duration: 0.35, ease: "power2.out" }}, {t:.2f});')
        self.js.append(f'tl.to("#{sid}", {{ opacity: 0, duration: 0.3, ease: "power2.in" }}, {until - 0.3:.2f});')

    def swap(self, t, img):
        self.n += 1
        iid = f"{self.sid}-img{self.n}"
        self.spots.insert(0, f'<img id="{iid}" src="{img}" width="{self.w}" height="{self.vh}" style="position:absolute;left:0;top:0;opacity:0">')
        self.js.append(f'tl.fromTo("#{iid}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5, ease: "power1.inOut" }}, {t:.2f});')

    def html(self):
        return (f'<div class="frame" id="{self.sid}-frame" style="left:{self.x}px;top:{self.y}px;width:{self.w}px;height:{self.vh + 34}px">'
                f'<div class="bar"><i></i><i></i><i></i><b>{self.label}</b></div>'
                f'<div class="view" style="top:34px;height:{self.vh}px"><div class="cam" id="{self.sid}-cam" style="width:{self.w}px;height:{self.vh}px">'
                f'<img src="{self.img}" width="{self.w}" height="{self.vh}">{"".join(self.spots)}</div></div></div>')

    def intro(self):
        return f'tl.fromTo("#{self.sid}-frame", {{ y: 40, scale: 0.97 }}, {{ y: 0, scale: 1, duration: 0.9, ease: "power3.out" }}, 0);'


def phone(pid, imgs, x, y, sw=405, sh=720):
    layers = "".join(f'<img id="{pid}-i{i}" src="{src}" style="opacity:{1 if i == 0 else 0}">' for i, src in enumerate(imgs))
    return f'<div class="phone" id="{pid}" style="left:{x}px;top:{y}px;width:{sw + 26}px;height:{sh + 26}px"><div class="scr">{layers}</div></div>'


def show(sel, t, d=0.5, fromy=24):
    return f'tl.fromTo("{sel}", {{ opacity: 0, y: {fromy} }}, {{ opacity: 1, y: 0, duration: {d}, ease: "power3.out" }}, {t:.2f});'


def fade(sel, t, d=0.5):
    return f'tl.fromTo("{sel}", {{ opacity: 0 }}, {{ opacity: 1, duration: {d}, ease: "power1.inOut" }}, {t:.2f});'


def point(pid, icon, text, sub="", x=0, y=0, w=760):
    return f'<div class="pt" id="{pid}" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;opacity:0"><span class="ic">{ico(icon, 30)}</span><span>{text}{f"<small>{sub}</small>" if sub else ""}</span></div>'


def label(sid, text, x=210, y=40):
    return f'<div class="kicker" id="{sid}-kick" style="position:absolute;left:{x}px;top:{y}px">{text}</div>'


# ------------------------------------------------------------------ scenes
def s01():
    sid, d = "s01", dur("s01")
    css = f""".big {{ position:absolute; left:0; right:0; text-align:center; font: 700 76px/1.15 "Mukta"; letter-spacing:-.01em; }}
    .big em {{ font-style: normal; color: #8fd9c9; }}
    .row {{ position:absolute; left:0; right:0; top:520px; display:flex; justify-content:center; gap:28px; }}
    .row .c {{ display:flex; align-items:center; gap:16px; padding:22px 34px; border-radius:22px; background: rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.16); font: 600 40px "Mukta"; opacity:0; }}
    .row .c span {{ color:{ACCENT}; display:grid; }}"""
    html = (f'<div class="big" id="s01-l1" style="top:250px">Millions of older people in India<br><em>live on their own at home.</em></div>'
            f'<div class="row"><div class="c" id="s01-c1"><span>{ico("steps", 40)}</span>Fewer steps</div><div class="c" id="s01-c2"><span>{ico("moon", 40)}</span>Poorer sleep</div><div class="c" id="s01-c3"><span>{ico("pill", 40)}</span>A missed medicine</div></div>'
            f'<div class="big" id="s01-l2" style="top:720px;font-size:56px;opacity:0">The signs appear <em>days</em> before the emergency.</div>')
    js = "\n    ".join([f'tl.fromTo("#s01-l1", {{ scale: 1 }}, {{ scale: 1.03, duration: {at(sid, "fewer"):.2f}, ease: "none" }}, 0);',
                       show("#s01-c1", at(sid, "fewer")), show("#s01-c2", at(sid, "poorer")), show("#s01-c3", at(sid, "missed")),
                       show("#s01-l2", at(sid, "warning") , 0.7),
                       f'tl.to("#s01-l2", {{ opacity: 0, duration: 0.4 }}, {at(sid, "But") - 0.3:.2f});',
                       f'tl.to("#s01-l1, .row", {{ opacity: 0.25, duration: 0.5 }}, {at(sid, "But"):.2f});'])
    html += '<div class="big" id="s01-l3" style="top:720px;font-size:56px;opacity:0">But no one is watching closely enough.</div>'
    js += "\n    " + show("#s01-l3", at(sid, "But"), 0.6)
    return sid, d, css, html, js


def s02():
    sid, d = "s02", dur("s02")
    css = f""".brand {{ position:absolute; left:0; right:0; top:330px; display:flex; flex-direction:column; align-items:center; gap:18px; }}
    .mark {{ width:120px; height:120px; border-radius:32px; background:{TEAL}; display:grid; place-items:center; box-shadow: 0 20px 60px rgba(13,122,105,.5); }}
    .name {{ font: 700 96px/1 "Mukta"; letter-spacing:-.02em; }}
    .tag {{ font: 400 36px "Mukta"; color:#b9d6cf; }}
    .lap {{ position:absolute; left:610px; top:330px; width:700px; height:420px; border-radius:16px; overflow:hidden; box-shadow:0 30px 70px rgba(0,0,0,.5); opacity:0; }}
    .lap img {{ width:100%; height:100%; object-fit:cover; object-position: top left; }}
    .cap {{ position:absolute; font: 600 30px "Mukta"; text-align:center; width:440px; opacity:0; }}
    .cap small {{ display:block; font: 400 28px "Mukta"; color:#b9d6cf; }}"""
    html = (f'<div class="brand" id="s02-brand"><div class="mark">{ico("logo", 70, "#fff", 1.6)}</div><div class="name">Aegis Saathi</div><div class="tag">An early-warning system for seniors living at home</div></div>'
            + phone("s02-p1", ["assets/app/app_home.png"], 250, 280, 270, 480)
            + '<div class="lap" id="s02-lap"><img src="assets/shots/today.png"></div>'
            + phone("s02-p2", ["assets/shots/family.png"], 1400, 280, 270, 480)
            + '<div class="cap" id="s02-k1" style="left:165px;top:810px">Senior<small>Phone app and calls</small></div>'
            + '<div class="cap" id="s02-k2" style="left:740px;top:790px">Care coordinator<small>Prioritised daily list</small></div>'
            + '<div class="cap" id="s02-k3" style="left:1315px;top:810px">Family<small>Shared with consent</small></div>')
    t1 = at(sid, "It connects") - 0.2
    js = "\n    ".join([show("#s02-brand", 0.2, 0.9),
                       f'tl.to("#s02-brand", {{ y: -260, scale: 0.62, duration: 0.9, ease: "power3.inOut" }}, {t1:.2f});',
                       f'tl.set("#s02-p1, #s02-p2", {{ opacity: 0 }}, 0);',
                       show("#s02-p1", at(sid, "phone"), 0.6, 40), show("#s02-k1", at(sid, "phone") + 0.2),
                       show("#s02-lap", at(sid, "coordinator"), 0.6, 40), show("#s02-k2", at(sid, "coordinator") + 0.2),
                       show("#s02-p2", at(sid, "family"), 0.6, 40), show("#s02-k3", at(sid, "family") + 0.2)])
    return sid, d, css, html, js


def s03():
    sid, d = "s03", dur("s03")
    html = (label(sid, "For the senior · Phone app", 210, 70)
            + phone("s03-p1", ["assets/app/app_home.png"], 240, 150)
            + phone("s03-p2", ["assets/app/app_home_hi.png"], 720, 150)
            + point("s03-a", "user", "Big buttons, plain words", "Made for people who have never used an app", 1240, 330, 600)
            + point("s03-b", "check", "Hindi or English", "The whole app switches with one tap", 1240, 520, 600))
    js = "\n    ".join([show(f"#{sid}-kick", 0.2), show("#s03-p1", 0.05, 0.6, 30),
                       f'tl.set("#s03-p2", {{ opacity: 0 }}, 0);',
                       show("#s03-a", at(sid, "Big")), show("#s03-p2", at(sid, "Hindi") - 0.3, 0.7, 50), show("#s03-b", at(sid, "Hindi"))])
    return sid, d, "", html, js


def s04():
    sid, d = "s04", dur("s04")
    html = (label(sid, "Daily check-in", 210, 70)
            + phone("s04-p", ["assets/app/app_home.png", "assets/app/app_checkin.png"], 330, 150)
            + point("s04-a", "heart", "How do you feel today?", "Fine, a bit weak, or not well", 1000, 280, 760)
            + point("s04-b", "pill", "Did you take your medicine?", "Taken, later, or skipped", 1000, 460, 760)
            + point("s04-c", "check", "Care manager told at once", "The answer reaches their list immediately", 1000, 640, 760))
    js = "\n    ".join([show(f"#{sid}-kick", 0.2), show("#s04-p", 0.05, 0.6, 30),
                       show("#s04-a", at(sid, "how")), show("#s04-b", at(sid, "medicine")),
                       fade("#s04-p-i1", at(sid, "One tap")), show("#s04-c", at(sid, "care manager"))])
    return sid, d, "", html, js


def s05():
    sid, d = "s05", dur("s05")
    css = f""".bub {{ position:absolute; max-width:760px; padding:16px 24px; border-radius:22px; font: 400 30px/1.35 "Mukta"; opacity:0; }}
    .bub b {{ display:block; font: 700 28px "Mukta"; letter-spacing:.08em; text-transform:uppercase; margin-bottom:2px; }}
    .ai {{ background: rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.16); }} .ai b {{ color:#8fd9c9; }}
    .me {{ background:#e1f3ee; color:{INK}; }} .me b {{ color:{TEAL}; }}"""
    lines = [("ai", "Saathi", "Hello Kamla Devi! How are you feeling today?", "check-in call", 1000, 150),
             ("me", "Kamla", "I feel a little dizzy and weak since yesterday.", "health", 1080, 290),
             ("ai", "Saathi", "Did you take your medicine? Just say yes or no.", "medicine", 1000, 430),
             ("me", "Kamla", "I took my morning medicine.", "sleep", 1080, 570),
             ("ai", "Saathi", "How did you sleep last night, and is your appetite okay?", "appetite", 1000, 680),
             ("me", "Kamla", "Did not sleep well, maybe four hours.", "slept", 1080, 820)]
    html = label(sid, "AI check-in call · real call on the phone app", 210, 70) + phone("s05-p", ["assets/app/app_ringing2.png", "assets/app/c2_reply0.png", "assets/app/c2_reply2.png"], 330, 150)
    js = [show(f"#{sid}-kick", 0.2), show("#s05-p", 0.05, 0.6, 30), fade("#s05-p-i1", at(sid, "check-in call")), fade("#s05-p-i2", at(sid, "Kamla"))]
    for i, (cls, who, text, word, x, y) in enumerate(lines):
        html += f'<div class="bub {cls}" id="s05-b{i}" style="left:{x}px;top:{y}px"><b>{who}</b>{text}</div>'
        t = at(sid, word)
        js.append(show(f"#s05-b{i}", t, 0.45, 16))
    # the first lines step back as the conversation grows, so the newest stays the brightest
    js.append(f'tl.to("#s05-b0", {{ opacity: 0.45, duration: 0.4 }}, {at(sid, "appetite"):.2f});')
    return sid, d, css, html, "\n    ".join(js)


def screen_scene(sid, img, chapter, beats, extra_html="", extra_css="", extra_js=None):
    d = dur(sid)
    sc = Screen(sid, img, chapter)
    beats(sc, d)
    html = sc.html() + extra_html
    js = [sc.intro()] + sc.js + (extra_js or [])
    return sid, d, extra_css, html, "\n    ".join(js)


R = RECTS


def s06():
    sid = "s06"
    def b(sc, d):
        sc.zoom(at(sid, "urgency") - 0.3, R["today"]["filters"], 1.55)
        sc.spot(at(sid, "urgent"), R["today"]["filters"], at(sid, "Each person"))
        sc.zoom(at(sid, "Each person") - 0.2, R["today"]["firstRow"], 1.9)
        sc.spot(at(sid, "Each person") + 0.2, R["today"]["firstRow"], d - 0.4)
    return screen_scene(sid, "assets/shots/today.png", "Care portal · Today", b)


def s07():
    sid = "s07"
    li3 = [859, 440, 882, 49]
    def b(sc, d):
        sc.zoom(0.8, R["reasons"]["reasons"], 1.45)
        sc.spot(at(sid, "eighty-five"), R["reasons"]["r0"], at(sid, "her activity"))
        sc.spot(at(sid, "her activity"), li3, at(sid, "pain") - 0.1)
        sc.spot(at(sid, "pain") - 0.1, R["reasons"]["r3"], at(sid, "Each reason"))
        sc.spot(at(sid, "Each reason"), R["reasons"]["r1"], d - 0.4)
    return screen_scene(sid, "assets/shots/reasons.png", "Care portal · Why they're on the list", b)


def s08():
    sid = "s08"
    def b(sc, d):
        sc.zoom(0.6, R["readings"]["tiles"], 1.5)
        sc.spot(at(sid, "fourteen"), R["readings"]["steps"], at(sid, "trends"))
        sc.spot(at(sid, "blood pressure"), R["readings"]["bp"], d - 0.4)
    return screen_scene(sid, "assets/shots/readings.png", "Care portal · Health readings", b)


def s09():
    sid = "s09"
    call_item = [859, 643, 882, 76]
    def b(sc, d):
        sc.zoom(0.5, [859, 560, 882, 520], 1.55)
        sc.spot(at(sid, "lands"), call_item, at(sid, "the full"))
        sc.spot(at(sid, "the full"), R["kamla"]["tx"], at(sid, "flag"))
        sc.spot(at(sid, "flag"), [1078, 703, 330, 40], d - 0.4)
    return screen_scene(sid, "assets/shots/kamla.png", "Care portal · Check-in call result", b)


def s10():
    sid, d = "s10", dur("s10")
    sc = Screen(sid, "assets/shots/sos.png", "Care portal · Emergency alert", x=760, y=170, w=1080)
    sc.spot(at(sid, "reaches"), R["sos"]["sosBar"], at(sid, "confirms"))
    sc.spot(at(sid, "confirms"), R["sos"]["sosActs"], d - 0.4)
    html = label(sid, "Emergency SOS", 210, 70) + phone("s10-p", ["assets/app/app_sos_holding.png", "assets/app/app_sos_count.png", "assets/app/app_sos_done.png"], 210, 150) + sc.html()
    js = [show(f"#{sid}-kick", 0.2), show("#s10-p", 0.05, 0.6, 30), fade("#s10-p-i1", at(sid, "holds") + 0.3), fade("#s10-p-i2", at(sid, "reaches") - 0.4),
          f'tl.set("#s10-frame", {{ opacity: 0 }}, 0);', show("#s10-frame", at(sid, "reaches") - 0.5, 0.7, 40)] + sc.js
    return sid, d, "", html, "\n    ".join(js)


def s11():
    sid, d = "s11", dur("s11")
    css = f""".st {{ position:absolute; top:300px; width:330px; text-align:center; opacity:0; }}
    .st .ring {{ width:150px; height:150px; margin:0 auto 22px; border-radius:50%; display:grid; place-items:center; background: rgba(143,217,201,.12); border:2px solid rgba(143,217,201,.35); color:#8fd9c9; }}
    .st.alert .ring {{ background: rgba(240,106,94,.16); border-color: rgba(240,106,94,.6); color:#ff9d93; }}
    .st h3 {{ font: 700 38px "Mukta"; margin:0; }} .st p {{ font: 400 28px/1.35 "Mukta"; color:#b9d6cf; margin:6px 0 0; }}
    .ln {{ position:absolute; top:375px; height:3px; background: rgba(143,217,201,.5); transform-origin: 0 50%; }}
    .out {{ position:absolute; top:690px; left:0; right:0; display:flex; justify-content:center; gap:22px; }}
    .out .o {{ padding:14px 26px; border-radius:16px; font: 600 28px "Mukta"; background: rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.16); opacity:0; }}
    .out .o.r {{ background: rgba(240,106,94,.16); border-color: rgba(240,106,94,.5); }}"""
    steps = [("fall", "Hard impact", "The phone feels a fall", "impact"), ("pause", "Then stillness", "No movement after it", "stillness"),
             ("phone", "Are you okay?", "A 30-second check on screen", "asks"), ("warn", "Alert raised", "Coordinator alerted at once", "raised")]
    html = label(sid, "Fall detection on the phone", 210, 70)
    js = [show(f"#{sid}-kick", 0.2)]
    for i, (ic, h, p, word) in enumerate(steps):
        x = 150 + i * 430
        html += f'<div class="st{" alert" if i == 3 else ""}" id="s11-st{i}" style="left:{x}px"><div class="ring">{ico(ic, 64)}</div><h3>{h}</h3><p>{p}</p></div>'
        js.append(show(f"#s11-st{i}", at(sid, word) - 0.1, 0.5))
        if i:
            html += f'<div class="ln" id="s11-ln{i}" style="left:{x - 430 + 330 // 2 + 85}px;width:{430 - 170}px"></div>'
            js.append(f'tl.fromTo("#s11-ln{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.4, ease: "power2.out" }}, {at(sid, word) - 0.3:.2f});')
    html += ('<div class="out"><div class="o" id="s11-o1">"I\'m okay" → logged</div><div class="o r" id="s11-o2">"I need help" → emergency</div>'
             '<div class="o r" id="s11-o3">No answer in 30 s → emergency</div></div>')
    js += [show("#s11-o1", at(sid, "okay"), 0.4), show("#s11-o2", at(sid, "help"), 0.4), show("#s11-o3", at(sid, "thirty"), 0.4)]
    return sid, d, css, html, "\n    ".join(js)


def s12():
    sid = "s12"
    def b(sc, d):
        sc.zoom(0.5, R["followup"]["dialog"], 1.45)
        sc.spot(at(sid, "useful"), R["followup"]["useful"], at(sid, "Saathi learns"))
        sc.spot(at(sid, "Saathi learns"), R["followup"]["dialog"], d - 0.4, pad=4)
    return screen_scene(sid, "assets/shots/followup.png", "Care portal · Log follow-up", b)


def s13():
    sid = "s13"
    workload = [390, 228, 1376, 330]
    def b(sc, d):
        sc.spot(at(sid, "people monitored"), [390, 88, 332, 116], at(sid, "who needs"))
        sc.spot(at(sid, "who needs"), [738, 88, 332, 116], at(sid, "open"))
        sc.spot(at(sid, "open"), [1086, 88, 332, 116], at(sid, "response"))
        sc.spot(at(sid, "response"), [1434, 88, 332, 116], at(sid, "workload"))
        sc.zoom(at(sid, "workload") - 0.3, workload, 1.3)
        sc.spot(at(sid, "workload"), workload, d - 0.4)
    return screen_scene(sid, "assets/shots/overview.png", "Operations · Overview", b)


def s14():
    sid = "s14"
    k = [[390 + i * 348, 88, 332, 116] for i in range(4)]
    def b(sc, d):
        sc.zoom(0.5, [390, 88, 1376, 380], 1.3)
        sc.spot(at(sid, "caught"), k[0], at(sid, "a median"))
        sc.spot(at(sid, "a median"), k[2], at(sid, "fewer"))
        sc.spot(at(sid, "fewer"), k[3], at(sid, "The limits") - 0.5)
        sc.swap(at(sid, "The limits") - 0.4, "assets/shots/method.png")
        sc.reset(at(sid, "The limits") - 0.6, 0.6)
        sc.zoom(at(sid, "The limits"), R["method"]["method"], 1.35)
        sc.spot(at(sid, "listed"), R["method"]["method"], d - 0.4, pad=4)
    return screen_scene(sid, "assets/shots/accuracy.png", "Operations · Alert accuracy", b)


def s15():
    sid, d = "s15", dur("s15")
    html = (label(sid, "Family view · shared with consent", 210, 70)
            + phone("s15-p", ["assets/shots/family.png"], 330, 150)
            + point("s15-a", "heart", "How they are today", "In plain words", 1000, 260, 760)
            + point("s15-b", "steps", "Steps and medicines this week", "Day by day", 1000, 430, 760)
            + point("s15-c", "user", "Who their care manager is", "", 1000, 600, 760)
            + point("s15-d", "shield", "No scores. No medical detail.", "The senior can stop sharing at any time", 1000, 740, 760))
    js = "\n    ".join([show(f"#{sid}-kick", 0.2), show("#s15-p", 0.05, 0.6, 30),
                       show("#s15-a", at(sid, "how they")), show("#s15-b", at(sid, "their steps")),
                       f'tl.to("#s15-p-i0", {{ y: -150, duration: 2.2, ease: "power1.inOut" }}, {at(sid, "their steps") - 0.2:.2f});',
                       show("#s15-c", at(sid, "who their")), show("#s15-d", at(sid, "No scores"))])
    return sid, d, "", html, js


def s16():
    sid, d = "s16", dur("s16")
    css = f""".end {{ position:absolute; left:0; right:0; top:330px; display:flex; flex-direction:column; align-items:center; gap:22px; }}
    .mark {{ width:132px; height:132px; border-radius:36px; background:{TEAL}; display:grid; place-items:center; box-shadow: 0 20px 70px rgba(13,122,105,.55); }}
    .name {{ font: 700 104px/1 "Mukta"; letter-spacing:-.02em; }}
    .tag {{ font: 400 42px "Mukta"; color:#cfe7e1; }}"""
    html = f'<div class="end"><div class="mark" id="s16-m">{ico("logo", 78, "#fff", 1.6)}</div><div class="name" id="s16-n">Aegis Saathi</div><div class="tag" id="s16-t">See who needs care today, before it becomes an emergency.</div></div>'
    js = "\n    ".join([f'tl.fromTo("#s16-m", {{ opacity: 0, scale: 0.8 }}, {{ opacity: 1, scale: 1, duration: 0.6, ease: "back.out(1.6)" }}, 0.0);',
                       show("#s16-n", at(sid, "Aegis"), 0.7), show("#s16-t", at(sid, "See"), 0.8)])
    return sid, d, css, html, js


SCENES = [s01, s02, s03, s04, s05, s06, s07, s08, s09, s10, s11, s12, s13, s14, s15, s16]


# ------------------------------------------------------------------ captions
def caption_groups(sid, offset):
    text = SCRIPT[sid]
    ws = WORDS[sid]["words"]
    cur, shown = 0, []
    for w in ws:                                # re-attach the punctuation edge-tts drops
        i = text.find(w["text"], cur)
        if i < 0:
            shown.append(w["text"]); continue
        j = i + len(w["text"])
        while j < len(text) and text[j] not in " ":
            j += 1
        shown.append(text[i:j]); cur = j
    groups, g = [], []
    for k, w in enumerate(ws):
        g.append(k)
        gap = ws[k + 1]["start"] - w["end"] if k + 1 < len(ws) else 9
        if len(g) >= 6 or shown[k][-1] in ".,:;?!" or gap > 0.25:
            groups.append(g); g = []
    if g:
        groups.append(g)
    out = []
    for g in groups:
        s = offset + LEAD.get(sid, 0.6) + ws[g[0]]["start"] - 0.05
        e = offset + LEAD.get(sid, 0.6) + ws[g[-1]]["end"] + 0.18
        out.append((round(s, 2), round(e, 2), " ".join(shown[k] for k in g)))
    for a, b in zip(out, out[1:]):              # never two on screen
        if a[1] > b[0]:
            out[out.index(a)] = (a[0], b[0] - 0.02, a[2])
    return out


def build():
    t, hosts, audio, caps = 0.0, [], [], []
    for fn in SCENES:
        sid, d, css, html, js = fn()
        open(os.path.join(ROOT, "compositions", f"{sid}.html"), "w", encoding="utf-8").write(scene_file(sid, css, html, js, d))
        hosts.append(f'      <div id="{sid}" class="clip" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>')
        v = WORDS[sid]
        audio.append(f'      <audio id="vo-{sid}" src="{v["file"]}" data-start="{t + LEAD.get(sid, 0.6):.2f}" data-duration="{v["duration"]:.2f}" data-track-index="3" data-volume="1"></audio>')
        caps += caption_groups(sid, t)
        t += d
    total = round(t, 2)
    cap_html, cap_js = [], []
    for i, (s, e, text) in enumerate(caps):
        cap_html.append(f'<div class="cg" id="cap{i}"><span>{text}</span></div>')
        cap_js.append(f'tl.fromTo("#cap{i}", {{ opacity: 0, y: 8 }}, {{ opacity: 1, y: 0, duration: 0.14, ease: "power2.out" }}, {s:.2f});'
                      f' tl.to("#cap{i}", {{ opacity: 0, duration: 0.1, ease: "power2.in" }}, {e - 0.1:.2f});'
                      f' tl.set("#cap{i}", {{ opacity: 0, visibility: "hidden" }}, {e:.2f});')
    open(os.path.join(ROOT, "compositions", "captions.html"), "w", encoding="utf-8").write(f"""<template>
  <style>
    {FONT}
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    .cg {{ position: absolute; left: 0; right: 0; bottom: 64px; text-align: center; opacity: 0; overflow: visible; }}
    .cg span {{ display: inline-block; max-width: 1500px; padding: 10px 26px 12px; border-radius: 14px; background: rgba(4, 18, 16, .78);
      color: #fff; font: 600 40px/1.3 "Mukta", sans-serif; letter-spacing: .005em; }}
  </style>
  <div id="root" data-composition-id="captions" data-width="{W}" data-height="{H}">
    {chr(10).join(cap_html)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {chr(10).join(cap_js)}
    window.__timelines["captions"] = tl;
  </script>
</template>
""")
    music = (f'      <audio id="music" src="assets/music/bed.mp3" data-start="0" data-duration="{total:.2f}" data-track-index="4" data-volume="0.14" data-fade-in="1.5" data-fade-out="3"></audio>\n'
             if MUSIC else "")
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: 1920px; height: 1080px; overflow: hidden; background: {NIGHT}; }}
      #main-bg {{ position: absolute; inset: 0; background: {NIGHT}; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total:.2f}" data-width="{W}" data-height="{H}">
      <div id="main-bg"></div>
{chr(10).join(hosts)}
      <div id="captions" class="clip" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{total:.2f}" data-track-index="2" data-track-kind="captions" data-width="{W}" data-height="{H}" style="z-index: 10"></div>
{chr(10).join(audio)}
{music}    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
""")
    print("scenes", len(SCENES), "captions", len(caps), "length", total, "s", "music" if MUSIC else "no music yet")


build()
