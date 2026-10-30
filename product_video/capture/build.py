"""Builds the Samarth Saathi product film from the narration timings and the real captured screens.
python build.py  ->  ../index.html, ../compositions/*.html
Every scene is timed to its own voice clip: highlights land on the word that names them."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
WORDS = {s["id"]: s for s in json.load(open(os.path.join(ROOT, "assets", "voice", "words.json"), encoding="utf-8"))}
SCRIPT = {s["id"]: s["text"] for s in json.load(open(os.path.join(HERE, "script.json"), encoding="utf-8"))}
W, H = 1920, 1080
LEAD = {"s01": 1.2}
TAIL = {"s13": 3.6}

# Samarth's palette
PLUM, PLUM_D, NIGHT, CREAM, SAFF, BLUSH = "#761f58", "#4a1137", "#2a0a1f", "#faf8f5", "#f7941e", "#f6edf2"

FONT = """@font-face { font-family: "Mukta"; src: url("assets/fonts/mukta_regular.ttf") format("truetype"); font-weight: 400; }
@font-face { font-family: "Mukta"; src: url("assets/fonts/mukta_semibold.ttf") format("truetype"); font-weight: 600; }
@font-face { font-family: "Mukta"; src: url("assets/fonts/mukta_bold.ttf") format("truetype"); font-weight: 700; }"""

ICON = {
    "check": '<path d="M5.2,12.6l4.4,4.4L18.8,7.6"/>',
    "phone": '<path d="M6.2,3.8h3l1.5,3.9-1.9,1.4a11,11 0 0 0 4.1,4.1l1.4,-1.9 3.9,1.5v3A2.2,2.2 0 0 1 15.9,19.9C9.2,19.3 4.7,14.8 4.1,8.1A2.2,2.2 0 0 1 6.2,3.8z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12,7.4V12l3.2,1.9"/>',
    "user": '<circle cx="12" cy="7.5" r="3.8"/><path d="M4.6,20.4C5.2,16.8 8.2,14.8 12,14.8S18.8,16.8 19.4,20.4"/>',
    "heart": '<path d="M12,19.6C5.5,14.3 3.2,11.5 3.2,8.5A4.6,4.6 0 0 1 12,6.7A4.6,4.6 0 0 1 20.8,8.5C20.8,11.5 18.5,14.3 12,19.6z"/>',
    "shield": '<path d="M12,3l7.2,2.8v5.6c0,4.6 -3.1,8 -7.2,9.6C7.9,19.4 4.8,16 4.8,11.4V5.8z"/><path d="M8.8,12l2.4,2.4L15.6,9.6"/>',
    "pill": '<g transform="rotate(-45 12 12)"><path d="M8,8.2H16A3.8,3.8 0 0 1 16,15.8H8A3.8,3.8 0 0 1 8,8.2z"/><path d="M12,8.2V15.8"/></g>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3,12h18"/><path d="M12,3a14,14 0 0 1 0,18a14,14 0 0 1 0,-18z"/>',
    "key": '<circle cx="8" cy="14" r="4"/><path d="M11,11l8,-8"/><path d="M16,6l3,3"/>',
    "speaker": '<path d="M4,9.5h3.5L12,5.5v13l-4.5,-4H4z"/><path d="M15.5,9a4,4 0 0 1 0,6"/><path d="M18,6.5a7.5,7.5 0 0 1 0,11"/>',
    "mic": '<rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M5.8,11.5a6.2,6.2 0 0 0 12.4,0"/><path d="M12,17.7V20.5"/>',
    "warn": '<path d="M12,3.6L21,19.4H3z"/><path d="M12,9.8v4.4"/><path d="M12,17h.01"/>',
    "pin": '<path d="M12,21s-6.5-5.6-6.5-11a6.5,6.5 0 0 1 13,0c0,5.4-6.5,11-6.5,11z"/><circle cx="12" cy="10" r="2.4"/>',
}


def ico(n, size=28):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICON[n]}</svg>'


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
    .bg {{ position: absolute; inset: 0; background: radial-gradient(120% 90% at 15% 0%, #8a2a69 0%, {PLUM_D} 45%, {NIGHT} 100%); }}
    .frame {{ position: absolute; overflow: hidden; border-radius: 18px; background: #fff; box-shadow: 0 30px 80px rgba(0,0,0,.45), 0 0 0 1px rgba(255,255,255,.1); }}
    .bar {{ position: absolute; left: 0; right: 0; top: 0; height: 34px; background: #efe6eb; display: flex; align-items: center; gap: 8px; padding-left: 16px; z-index: 3; }}
    .bar i {{ width: 11px; height: 11px; border-radius: 50%; background: #d9c8d2; }}
    .bar b {{ margin-left: 18px; font: 600 15px "Mukta"; color: #6b5562; }}
    .view {{ position: absolute; left: 0; right: 0; bottom: 0; overflow: hidden; }}
    .cam {{ position: absolute; left: 0; top: 0; transform-origin: 0 0; }}
    .cam img {{ display: block; }}
    .spot {{ position: absolute; border-radius: 14px; border: 4px solid {SAFF}; box-shadow: 0 0 0 4000px rgba(42,10,31,.40), 0 0 26px rgba(247,148,30,.6); opacity: 0; }}
    .kicker {{ font: 700 30px "Mukta"; letter-spacing: .16em; text-transform: uppercase; color: {SAFF}; }}
    .title {{ font: 700 62px/1.08 "Mukta"; color: #fff; }}
    .phone {{ position: absolute; border-radius: 54px; background: #0b0a0b; padding: 13px; box-shadow: 0 30px 70px rgba(0,0,0,.55), 0 0 0 2px rgba(255,255,255,.1); }}
    .phone .scr {{ position: relative; width: 100%; height: 100%; border-radius: 42px; overflow: hidden; background: #fff; }}
    .phone .scr img {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; object-fit: cover; object-position: top; }}
    .pt {{ display: flex; align-items: flex-start; gap: 20px; font: 600 40px/1.22 "Mukta"; color: #fff; }}
    .pt .ic {{ flex: none; width: 60px; height: 60px; border-radius: 18px; display: grid; place-items: center; background: rgba(247,148,30,.16); color: {SAFF}; }}
    .pt small {{ display: block; font: 400 28px/1.35 "Mukta"; color: #e9cfdf; margin-top: 4px; }}
    .num {{ background: {SAFF} !important; color: {PLUM_D} !important; font: 700 30px "Mukta"; }}
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
    """A browser frame showing a 1920x1080 capture, with a camera that pushes in and highlights named boxes."""

    def __init__(self, sid, img, label, x=210, y=60, w=1500):
        self.sid, self.img, self.label, self.x, self.y, self.w = sid, img, label, x, y, w
        self.vh = round(w * 1080 / 1920)
        self.k = w / 1920
        self.js, self.layers, self.n = [], [], 0
        self.cam = f"#{sid}-cam"

    def rect(self, r):
        return [v * self.k for v in r]

    def zoom(self, t, r, s, d=1.1):
        x, y, w, h = self.rect(r)
        cx, cy = x + w / 2, y + h / 2
        tx = min(0, max(self.w - s * self.w, self.w / 2 - s * cx))
        ty = min(0, max(self.vh - s * self.vh, self.vh / 2 - s * cy))
        self.js.append(f'tl.to("{self.cam}", {{ x: {tx:.1f}, y: {ty:.1f}, scale: {s}, duration: {d}, ease: "power2.inOut" }}, {t:.2f});')

    def reset(self, t, d=0.9):
        self.js.append(f'tl.to("{self.cam}", {{ x: 0, y: 0, scale: 1, duration: {d}, ease: "power2.inOut" }}, {t:.2f});')

    def spot(self, t, r, until, pad=8):
        x, y, w, h = self.rect(r)
        self.n += 1
        sid = f"{self.sid}-sp{self.n}"
        self.layers.append(f'<div class="spot" id="{sid}" style="left:{x - pad:.0f}px;top:{y - pad:.0f}px;width:{w + 2 * pad:.0f}px;height:{h + 2 * pad:.0f}px"></div>')
        self.js.append(f'tl.fromTo("#{sid}", {{ opacity: 0, scale: 1.04 }}, {{ opacity: 1, scale: 1, duration: 0.35, ease: "power2.out" }}, {t:.2f});')
        self.js.append(f'tl.to("#{sid}", {{ opacity: 0, duration: 0.3, ease: "power2.in" }}, {until - 0.3:.2f});')

    def swap(self, t, img):
        self.n += 1
        iid = f"{self.sid}-img{self.n}"
        self.layers.insert(0, f'<img id="{iid}" src="{img}" width="{self.w}" height="{self.vh}" style="position:absolute;left:0;top:0;opacity:0">')
        self.js.append(f'tl.fromTo("#{iid}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.45, ease: "power1.inOut" }}, {t:.2f});')

    def html(self):
        return (f'<div class="frame" id="{self.sid}-frame" style="left:{self.x}px;top:{self.y}px;width:{self.w}px;height:{self.vh + 34}px">'
                f'<div class="bar" data-layout-ignore><i></i><i></i><i></i><b>{self.label}</b></div>'
                f'<div class="view" style="top:34px;height:{self.vh}px"><div class="cam" id="{self.sid}-cam" style="width:{self.w}px;height:{self.vh}px">'
                f'<img src="{self.img}" width="{self.w}" height="{self.vh}">{"".join(self.layers)}</div></div></div>')

    def intro(self):
        return f'tl.fromTo("#{self.sid}-frame", {{ y: 40, scale: 0.97 }}, {{ y: 0, scale: 1, duration: 0.9, ease: "power3.out" }}, 0);'


class Phone:
    """A phone showing real screenshots that cross-fade on cue."""

    def __init__(self, pid, imgs, x, y, sw=400, sh=889):
        self.pid, self.imgs, self.x, self.y, self.sw, self.sh = pid, imgs, x, y, sw, sh
        self.js = []

    def to(self, t, i):
        self.js.append(f'tl.fromTo("#{self.pid}-i{i}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4, ease: "power1.inOut" }}, {t:.2f});')

    def html(self):
        layers = "".join(f'<img id="{self.pid}-i{i}" src="{src}" style="opacity:{1 if i == 0 else 0}">' for i, src in enumerate(self.imgs))
        return (f'<div class="phone" id="{self.pid}" style="left:{self.x}px;top:{self.y}px;width:{self.sw + 26}px;height:{self.sh + 26}px">'
                f'<div class="scr">{layers}</div></div>')

    def intro(self, t=0.1):
        return f'tl.fromTo("#{self.pid}", {{ y: 60, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.8, ease: "power3.out" }}, {t:.2f});'


def show(sel, t, d=0.5, fromy=24):
    return f'tl.fromTo("{sel}", {{ opacity: 0, y: {fromy} }}, {{ opacity: 1, y: 0, duration: {d}, ease: "power3.out" }}, {t:.2f});'


def point(pid, icon, text, sub="", x=0, y=0, w=820, num=None):
    badge = f'<span class="ic num">{num}</span>' if num else f'<span class="ic">{ico(icon, 32)}</span>'
    return f'<div class="pt" id="{pid}" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;opacity:0">{badge}<span>{text}{f"<small>{sub}</small>" if sub else ""}</span></div>'


def head(sid, kicker, title, x=860, y=120, w=920):
    return (f'<div id="{sid}-k" class="kicker" style="position:absolute;left:{x}px;top:{y}px;opacity:0">{kicker}</div>'
            f'<div id="{sid}-t" class="title" style="position:absolute;left:{x}px;top:{y + 44}px;width:{w}px;opacity:0">{title}</div>')


def head_js(sid, t=0.3):
    return [show(f"#{sid}-k", t), show(f"#{sid}-t", t + 0.12)]


def screen_scene(sid, img, label, beats, extra_html="", extra_js=None):
    d = dur(sid)
    sc = Screen(sid, img, label)
    beats(sc, d)
    return sid, d, "", sc.html() + extra_html, "\n    ".join([sc.intro()] + sc.js + (extra_js or []))


def phone_scene(sid, phones, points, kicker, title, extra_html="", extra_js=None):
    d = dur(sid)
    html = "".join(p.html() for p in phones) + head(sid, kicker, title) + "".join(points) + extra_html
    js = [p.intro(0.1 + 0.15 * i) for i, p in enumerate(phones)] + [j for p in phones for j in p.js] + head_js(sid) + (extra_js or [])
    return sid, d, "", html, "\n    ".join(js)


SH = "assets/shots/"
AP = "assets/app/"


# ------------------------------------------------------------------ scenes
def s01():
    sid = "s01"
    def b(sc, d):
        sc.zoom(0.4, [360, 160, 640, 470], 1.35, d=2.6)
        sc.reset(at(sid, "Meet") - 0.4)
        sc.spot(at(sid, "Samarth Saathi"), [378, 522, 264, 51], d - 0.3)
    return screen_scene(sid, SH + "site_hero.png", "samarth.community", b)


def s02():
    sid = "s02"
    cards = [[380, 96, 372, 438], [774, 96, 372, 438], [1168, 96, 372, 438]]
    def b(sc, d):
        sc.swap(at(sid, "checks in") - 0.6, SH + "site_features.png")
        for i, (word, nxt) in enumerate((("checks", "rings"), ("rings", "brings"), ("brings", None))):
            sc.spot(at(sid, word), cards[i], at(sid, nxt) if nxt else d - 0.2)
    return screen_scene(sid, SH + "site_saathi.png", "samarth.community · Saathi", b)


def s03():
    sid = "s03"
    def b(sc, d):
        sc.zoom(at(sid, "Choose") - 0.3, [408, 273, 699, 159], 1.35)
        sc.spot(at(sid, "Choose"), [408, 273, 699, 159], at(sid, "Then"))
        sc.zoom(at(sid, "Then") - 0.2, [381, 495, 1107, 270], 1.3)
        sc.spot(at(sid, "parent's name"), [381, 495, 1107, 270], d - 0.2)
    return screen_scene(sid, SH + "buy_form.png", "samarth.community / Get Saathi", b)


def s04():
    sid = "s04"
    def b(sc, d):
        sc.spot(0.6, [465, 246, 990, 579], at(sid, "In seconds"))
        sc.swap(at(sid, "In seconds") - 0.3, SH + "buy_success2.png")
        sc.spot(at(sid, "assigns"), [660, 600, 600, 60], at(sid, "one-time"))
        sc.spot(at(sid, "one-time"), [660, 384, 600, 186], at(sid, "WhatsApp"))
        sc.spot(at(sid, "WhatsApp"), [936, 507, 183, 36], d - 0.2, pad=12)
    return screen_scene(sid, SH + "buy_checkout.png", "Razorpay · Test mode", b)


def s05():
    sid = "s05"
    ph = Phone(f"{sid}-ph", [AP + "slide1.png", AP + "slide2.png", AP + "slide3.png", AP + "slide6.png"], 330, 70)
    for i, t in enumerate((2.6, 4.4, 6.2), 1):
        ph.to(t, i)
    pts = [point(f"{sid}-p1", "heart", "A warm, short welcome", "Six simple slides", 860, 430),
           point(f"{sid}-p2", "speaker", "Every screen read aloud", "In Hindi or English", 860, 600)]
    return phone_scene(sid, [ph], pts, "On your parent's phone", "Saathi says hello.",
                       extra_js=[show(f"#{sid}-p1", at(sid, "short")), show(f"#{sid}-p2", at(sid, "read"))])


def s06():
    sid = "s06"
    ph = Phone(f"{sid}-ph", [AP + "setup_lang.png", AP + "setup_name.png", AP + "setup_code.png", AP + "home_new.png"], 330, 70)
    ph.to(at(sid, "type") - 0.2, 1)
    ph.to(at(sid, "enter") - 0.2, 2)
    ph.to(at(sid, "The phone") - 0.1, 3)
    pts = [point(f"{sid}-p1", "", "Choose the language", "", 860, 380, num=1),
           point(f"{sid}-p2", "", "Type their name", "", 860, 500, num=2),
           point(f"{sid}-p3", "", "Enter the Saathi code", "SAATHI-X4U52V", 860, 620, num=3),
           point(f"{sid}-p4", "check", "Linked to Rajesh Verma", "Their Samarth Care Manager", 860, 790)]
    return phone_scene(sid, [ph], pts, "One-minute setup", "Redeem the code.",
                       extra_js=[show(f"#{sid}-p1", at(sid, "Choose")), show(f"#{sid}-p2", at(sid, "type")),
                                 show(f"#{sid}-p3", at(sid, "enter")), show(f"#{sid}-p4", at(sid, "The phone"))])


def s07():
    sid = "s07"
    a = Phone(f"{sid}-a", [AP + "home_checkin.png"], 230, 70)
    b = Phone(f"{sid}-b", [AP + "home_next.png"], 720, 70)
    pts = [point(f"{sid}-p1", "clock", "One thing at a time", "Check-in first, then the next dose", 1240, 430, w=600),
           point(f"{sid}-p2", "check", "Updates by itself", "All day, no tapping around", 1240, 640, w=600)]
    html = "".join(p.html() for p in (a, b)) + (f'<div id="{sid}-k" class="kicker" style="position:absolute;left:1240px;top:170px;opacity:0">Home screen</div>'
            f'<div id="{sid}-t" class="title" style="position:absolute;left:1240px;top:214px;width:600px;opacity:0">Always the next step.</div>') + "".join(pts)
    js = [a.intro(0.1), b.intro(at(sid, "next medicine") - 0.4)] + head_js(sid) + [show(f"#{sid}-p1", at(sid, "one thing")), show(f"#{sid}-p2", at(sid, "updates"))]
    return sid, dur(sid), "", html, "\n    ".join(js)


def s08():
    sid = "s08"
    ph = Phone(f"{sid}-ph", [AP + "home_dose.png", AP + "dose_ring.png"], 330, 70)
    ph.to(at(sid, "rings") - 0.2, 1)
    pts = [point(f"{sid}-p1", "phone", "Rings, even when locked", "", 860, 400),
           point(f"{sid}-p2", "check", "One big button: I took it", "", 860, 540),
           point(f"{sid}-p3", "warn", "A missed dose is flagged", "To the Care Manager, the same day", 860, 680)]
    return phone_scene(sid, [ph], pts, "Medicine reminders", "Never miss a dose.",
                       extra_js=[show(f"#{sid}-p1", at(sid, "rings")), show(f"#{sid}-p2", at(sid, "One big")), show(f"#{sid}-p3", at(sid, "missed"))])


def s09():
    sid = "s09"
    ph = Phone(f"{sid}-ph", [AP + "app_ringing.png", AP + "app_call1.png", AP + "app_call2.png"], 330, 150, sw=400, sh=711)
    ph.to(at(sid, "real") - 0.3, 1)
    ph.to(at(sid, "listens") - 0.2, 2)
    pts = [point(f"{sid}-p1", "phone", "A daily call from Saathi", "", 860, 400),
           point(f"{sid}-p2", "mic", "A real conversation", "Sleep, food, and whatever is on their mind", 860, 540),
           point(f"{sid}-p3", "shield", "Anything serious is flagged", "Straight to a person", 860, 720)]
    return phone_scene(sid, [ph], pts, "Daily check-in call", "Saathi calls, and listens.",
                       extra_js=[show(f"#{sid}-p1", at(sid, "Every day")), show(f"#{sid}-p2", at(sid, "real")), show(f"#{sid}-p3", at(sid, "flags"))])


def s10():
    sid = "s10"
    ph = Phone(f"{sid}-ph", [AP + "app_sos_sent.png"], 330, 150, sw=400, sh=711)
    art = f'<img id="{sid}-art" src="assets/ill/sos.svg" style="position:absolute;left:1160px;top:560px;width:540px;opacity:0">'
    pts = [point(f"{sid}-p1", "warn", "Hold SOS for 3 seconds", "", 860, 360),
           point(f"{sid}-p2", "pin", "Care Manager alerted, with location", "", 860, 480, w=900)]
    return phone_scene(sid, [ph], pts, "Emergency", "Help in one press.", extra_html=art,
                       extra_js=[show(f"#{sid}-p1", at(sid, "hold")), show(f"#{sid}-p2", at(sid, "alerted")), show(f"#{sid}-art", at(sid, "alerted") + 0.3)])


def s11():
    sid = "s11"
    def b(sc, d):
        sc.spot(at(sid, "who needs"), [390, 345, 420, 405], at(sid, "and why"))
        sc.spot(at(sid, "and why"), [849, 855, 891, 225], at(sid, "readings"))
        sc.swap(at(sid, "readings") - 0.3, SH + "portal_vitals.png")
        sc.spot(at(sid, "readings"), [840, 330, 924, 420], at(sid, "medicines"))
        sc.swap(at(sid, "medicines") - 0.3, SH + "portal_kamla_meds.png")
        sc.spot(at(sid, "medicines"), [849, 405, 906, 195], d - 0.2)
    return screen_scene(sid, SH + "portal_today.png", "Samarth Care Manager portal", b)


def s12():
    sid = "s12"
    ph = Phone(f"{sid}-ph", [AP + "../shots/family_home.png", AP + "../shots/family_home2.png"], 330, 70, sw=400, sh=867)
    ph.to(at(sid, "weekly") + 0.4, 1)
    pts = [point(f"{sid}-p1", "heart", "A calm weekly summary", "Medicines, steps and calls", 860, 430),
           point(f"{sid}-p2", "shield", "Only with their consent", "They can stop sharing any time", 860, 600)]
    return phone_scene(sid, [ph], pts, "For the family", "Peace of mind.",
                       extra_js=[show(f"#{sid}-p1", at(sid, "calm")), show(f"#{sid}-p2", at(sid, "consent"))])


def s13():
    sid = "s13"
    d = dur(sid)
    css = """.end { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
    .wm { font: 700 150px/1 "Mukta"; color: #fff; letter-spacing: -.02em; }
    .wm i { font-style: normal; color: %s; }
    .tag { display: inline-block; margin-left: 18px; vertical-align: 46px; font: 700 40px "Mukta"; color: %s; background: %s; border-radius: 999px; padding: 4px 26px; }
    .line { margin-top: 34px; font: 600 52px "Mukta"; color: #f3dfea; }
    .cta { margin-top: 44px; font: 700 34px "Mukta"; color: %s; background: %s; border-radius: 999px; padding: 16px 44px; }""" % (SAFF, PLUM_D, SAFF, PLUM_D, SAFF)
    html = (f'<img id="{sid}-art" src="assets/ill/family.svg" style="position:absolute;left:50%;top:40px;width:420px;margin-left:-210px;opacity:0">'
            f'<div class="end" style="padding-top:260px"><div id="{sid}-wm" class="wm" style="opacity:0">samarth<i>.</i><span class="tag">Saathi</span></div>'
            f'<div id="{sid}-line" class="line" style="opacity:0">Care that checks in, every day.</div>'
            f'<div id="{sid}-cta" class="cta" style="opacity:0">Get Saathi for your parent</div></div>')
    js = [show(f"#{sid}-art", 0.2, 0.8), show(f"#{sid}-wm", 0.5, 0.8), show(f"#{sid}-line", at(sid, "Care that")), show(f"#{sid}-cta", at(sid, "every day", end=True) + 0.3)]
    return sid, d, css, html, "\n    ".join(js)


SCENES = [s01, s02, s03, s04, s05, s06, s07, s08, s09, s10, s11, s12, s13]


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
        if len(g) >= 7 or shown[k][-1] in ".,:;?!" or gap > 0.25:
            groups.append(g); g = []
    if g:
        groups.append(g)
    out = []
    for g in groups:
        s = offset + LEAD.get(sid, 0.6) + ws[g[0]]["start"] - 0.05
        e = offset + LEAD.get(sid, 0.6) + ws[g[-1]]["end"] + 0.18
        out.append((round(s, 2), round(e, 2), " ".join(shown[k] for k in g)))
    for i in range(len(out) - 1):              # never two on screen
        if out[i][1] > out[i + 1][0]:
            out[i] = (out[i][0], out[i + 1][0] - 0.02, out[i][2])
    return out


def build():
    t, hosts, audio, caps = 0.0, [], [], []
    os.makedirs(os.path.join(ROOT, "compositions"), exist_ok=True)
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
                      f' tl.to("#cap{i}", {{ opacity: 0, duration: 0.1, ease: "power2.in" }}, {e - 0.1:.2f});')
    open(os.path.join(ROOT, "compositions", "captions.html"), "w", encoding="utf-8").write(f"""<template>
  <style>
    {FONT}
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    .cg {{ position: absolute; left: 0; right: 0; bottom: 54px; text-align: center; opacity: 0; overflow: visible; }}
    .cg span {{ display: inline-block; max-width: 1500px; padding: 10px 26px 12px; border-radius: 14px; background: rgba(42, 10, 31, .82);
      color: #fff; font: 600 40px/1.3 "Mukta", sans-serif; }}
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
      <audio id="music" src="assets/music/bed.wav" data-start="0" data-duration="{total:.2f}" data-track-index="4" data-volume="0.12" data-fade-in="1.5" data-fade-out="3"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
""")
    print("scenes", len(SCENES), "captions", len(caps), "length", total, "s")


build()
