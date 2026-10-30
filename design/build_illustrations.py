"""Builds the Aegis Saathi illustrations from hand-written SVG.

  design/illustrations/parts/<name>.svg   a character or object on its own grid (one <svg>, any viewBox)
  design/illustrations/scenes/<name>.svg  a 360x300 scene; <use-part name="dadi" transform="..."/> places a part

Outputs, from one source:
  android_app/app/src/main/res/drawable/ill_<scene>.xml   VectorDrawable (blob included: the app is light-only)
  coordinator_hub/static/illustrations/<scene>.svg       plain SVG without the blob (the web draws it in CSS)
  design/illustrations/sheet.html                        every scene side by side, to check the style is consistent

Only path / circle / ellipse / rect / g(transform) and fill / stroke / opacity are used, so the conversion is exact.
Run:  python design/build_illustrations.py
"""
import copy
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "design", "illustrations")
OUT_ANDROID = os.path.join(ROOT, "android_app", "app", "src", "main", "res", "drawable")
OUT_WEB = os.path.join(ROOT, "coordinator_hub", "static", "illustrations")
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)


def tag(el):
    return el.tag.split("}")[-1]


def load(path):
    return ET.parse(path).getroot()


def parts():
    out = {}
    for f in sorted(os.listdir(os.path.join(SRC, "parts"))):
        if f.endswith(".svg"):
            out[f[:-4]] = load(os.path.join(SRC, "parts", f))
    return out


def compose(scene, lib):
    """Replaces every <use-part name=.. transform=..> with a <g> holding that part's shapes (recursively)."""
    def walk(el):
        for i, ch in enumerate(list(el)):
            if tag(ch) == "use-part":
                p = lib[ch.get("name")]
                g = ET.Element("{%s}g" % SVG)
                if ch.get("transform"):
                    g.set("transform", ch.get("transform"))
                for k in ("opacity", "class"):
                    if ch.get(k):
                        g.set(k, ch.get(k))
                for sub in p:
                    if tag(sub) not in ("title", "desc", "defs"):
                        g.append(copy.deepcopy(sub))
                el.remove(ch)
                el.insert(i, g)
                walk(g)
            else:
                walk(ch)
    s = copy.deepcopy(scene)
    walk(s)
    return s


# ---------------------------------------------------------------- shapes -> path data
def f(n):
    return ("%.2f" % float(n)).rstrip("0").rstrip(".")


def ellipse_d(cx, cy, rx, ry):
    return (f"M{f(cx - rx)},{f(cy)}a{f(rx)},{f(ry)} 0 1,0 {f(2 * rx)},0"
            f"a{f(rx)},{f(ry)} 0 1,0 {f(-2 * rx)},0z")


def rect_d(x, y, w, h, rx=0, ry=None):
    ry = rx if ry is None else ry
    rx, ry = min(rx, w / 2), min(ry, h / 2)
    if not rx:
        return f"M{f(x)},{f(y)}h{f(w)}v{f(h)}h{f(-w)}z"
    return (f"M{f(x + rx)},{f(y)}h{f(w - 2 * rx)}a{f(rx)},{f(ry)} 0 0,1 {f(rx)},{f(ry)}v{f(h - 2 * ry)}"
            f"a{f(rx)},{f(ry)} 0 0,1 {f(-rx)},{f(ry)}h{f(-(w - 2 * rx))}a{f(rx)},{f(ry)} 0 0,1 {f(-rx)},{f(-ry)}"
            f"v{f(-(h - 2 * ry))}a{f(rx)},{f(ry)} 0 0,1 {f(rx)},{f(-ry)}z")


def shape_d(el):
    t, g = tag(el), lambda k, d=0: float(el.get(k, d))
    if t == "path":
        return el.get("d")
    if t == "circle":
        return ellipse_d(g("cx"), g("cy"), g("r"), g("r"))
    if t == "ellipse":
        return ellipse_d(g("cx"), g("cy"), g("rx"), g("ry"))
    if t == "rect":
        rx = el.get("rx")
        return rect_d(g("x"), g("y"), g("width"), g("height"), float(rx or 0), float(el.get("ry", rx or 0)))
    return None


# ---------------------------------------------------------------- VectorDrawable
TF = re.compile(r"(translate|scale|rotate)\s*\(([^)]*)\)")


def groups_for(transform):
    """SVG transform list -> nested Android <group> attribute sets, outermost first (exact for these three)."""
    out = []
    for name, args in TF.findall(transform or ""):
        a = [float(x) for x in re.split(r"[ ,]+", args.strip()) if x]
        if name == "translate":
            out.append({"translateX": a[0], "translateY": a[1] if len(a) > 1 else 0})
        elif name == "scale":
            out.append({"scaleX": a[0], "scaleY": a[1] if len(a) > 1 else a[0]})
        else:
            g = {"rotation": a[0]}
            if len(a) == 3:
                g.update(pivotX=a[1], pivotY=a[2])
            out.append(g)
    return out


def color(v):
    if not v or v == "none":
        return None
    v = v.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", v):
        v = "#" + "".join(c * 2 for c in v[1:])
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        raise ValueError("colour must be #rrggbb: " + v)
    return "#FF" + v[1:].upper()


CLIPS = {}


def to_vector(svg, name):
    CLIPS.clear()
    CLIPS.update({e.get("id"): e for e in svg.iter() if e.get("id")})
    vb = [float(x) for x in svg.get("viewBox").split()]
    w, h = vb[2], vb[3]
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             f'<!-- Generated by design/build_illustrations.py from design/illustrations/scenes/{name}.svg. Do not edit. -->',
             '<vector xmlns:android="http://schemas.android.com/apk/res/android"',
             f'    android:width="{f(w)}dp" android:height="{f(h)}dp"',
             f'    android:viewportWidth="{f(w)}" android:viewportHeight="{f(h)}">']

    def emit(el, depth, alpha, inherited):
        ind = "    " * depth
        t = tag(el)
        a = alpha * float(el.get("opacity", 1))
        style = dict(inherited)
        for k in ("fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "fill-rule"):
            if el.get(k) is not None:
                style[k] = el.get(k)
        if t in ("svg", "g"):
            gs = groups_for(el.get("transform")) if t == "g" else []
            if t == "g" and el.get("clip"):          # <g clip="blob">: children are cut to that shape
                gs = gs + [{}]
            for g in gs:
                attrs = " ".join(f'android:{k}="{f(v)}"' for k, v in g.items())
                lines.append(f"{ind}<group {attrs}>".replace("<group >", "<group>"))
                depth += 1
                ind = "    " * depth
            if t == "g" and el.get("clip"):
                lines.append(f'{ind}<clip-path android:pathData="{shape_d(CLIPS[el.get("clip")])}" />')
            for ch in el:
                emit(ch, depth, a, style)
            for _ in gs:
                depth -= 1
                lines.append("    " * depth + "</group>")
            return
        d = shape_d(el)
        if d is None:
            return
        if el.get("transform"):     # a transformed shape becomes a group around one path
            emit_g = ET.Element("g", {"transform": el.get("transform")})
            c = copy.deepcopy(el)
            del c.attrib["transform"]
            emit_g.append(c)
            emit(emit_g, depth, alpha, inherited)
            return
        fill = color(style.get("fill", "#000000"))
        stroke = color(style.get("stroke"))
        attrs = [f'android:pathData="{d}"']
        if fill:
            attrs.append(f'android:fillColor="{fill}"')
            fa = a * float(el.get("fill-opacity", 1))
            if fa < 1:
                attrs.append(f'android:fillAlpha="{f(fa)}"')
            if style.get("fill-rule") == "evenodd":
                attrs.append('android:fillType="evenOdd"')
        if stroke:
            attrs += [f'android:strokeColor="{stroke}"', f'android:strokeWidth="{f(style.get("stroke-width", 1))}"']
            if a < 1:
                attrs.append(f'android:strokeAlpha="{f(a)}"')
            if style.get("stroke-linecap"):
                attrs.append(f'android:strokeLineCap="{style["stroke-linecap"]}"')
            if style.get("stroke-linejoin"):
                attrs.append(f'android:strokeLineJoin="{style["stroke-linejoin"]}"')
        lines.append(f"{ind}<path " + ("\n" + ind + "    ").join(attrs) + " />")

    for ch in svg:
        emit(ch, 1, 1.0, {})
    lines.append("</vector>")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- web SVG + sheet
def strip_blob(svg):
    s = copy.deepcopy(svg)
    def walk(el):
        for ch in list(el):
            if "blob" in (ch.get("class") or "").split():
                el.remove(ch)
            else:
                walk(ch)
    walk(s)
    return s


def to_web(svg, name):
    s = copy.deepcopy(svg)
    ids = {e.get("id"): e for e in s.iter() if e.get("id")}
    defs = None
    for g in s.iter():
        if g.get("clip"):
            cid = f"{name}-{g.get('clip')}"
            if defs is None:
                defs = ET.Element("{%s}defs" % SVG)
                s.insert(0, defs)
            if defs.find(f".//*[@id='{cid}']") is None:
                cp = ET.SubElement(defs, "{%s}clipPath" % SVG, {"id": cid})
                ET.SubElement(cp, "{%s}path" % SVG, {"d": shape_d(ids[g.get("clip")])})
            g.set("clip-path", f"url(#{cid})")
            del g.attrib["clip"]
    for e in s.iter():                  # source-only markers; clipPath ids live in <defs> and are kept
        if e.get("class"):
            del e.attrib["class"]
        if e.get("id") in ids:
            del e.attrib["id"]
    for k in list(s.attrib):
        if k not in ("viewBox", "width", "height"):
            del s.attrib[k]
    # ElementTree writes the xmlns itself; setting it again duplicates the attribute (invalid XML)
    txt = ET.tostring(s, encoding="unicode")
    txt = re.sub(r"\s*xmlns:ns0=\"[^\"]*\"", "", txt).replace("ns0:", "")
    return re.sub(r">\s+<", "><", txt)


def main(only=None):
    lib = parts()
    os.makedirs(OUT_WEB, exist_ok=True)
    names = []
    for fn in sorted(os.listdir(os.path.join(SRC, "scenes"))):
        if not fn.endswith(".svg"):
            continue
        name = fn[:-4]
        if only and name not in only:
            continue
        svg = compose(load(os.path.join(SRC, "scenes", fn)), lib)
        vec = to_vector(svg, name)
        open(os.path.join(OUT_ANDROID, f"ill_{name}.xml"), "w", encoding="utf-8").write(vec)
        web = to_web(svg, name)
        open(os.path.join(OUT_WEB, f"{name}.svg"), "w", encoding="utf-8").write(web)
        os.makedirs(os.path.join(SRC, "build"), exist_ok=True)
        open(os.path.join(SRC, "build", f"{name}.svg"), "w", encoding="utf-8").write(web)
        names.append((name, len(vec.encode()), web))
        print(f"{name:22s} vector {len(vec.encode()) / 1024:5.1f} KB   web {len(web.encode()) / 1024:5.1f} KB")
    cards = "".join(f'<figure><div class="art">{full}</div><figcaption>{n} · {kb / 1024:.1f} KB</figcaption></figure>' for n, kb, full in names)
    open(os.path.join(SRC, "sheet.html"), "w", encoding="utf-8").write(
        "<!doctype html><meta charset=utf-8><title>Aegis Saathi illustrations</title><style>"
        "body{margin:0;padding:32px;background:#f3f6f5;font:15px system-ui;color:#3c4c48}"
        ".g{display:grid;grid-template-columns:repeat(4,1fr);gap:24px}"
        "figure{margin:0;background:#fff;border-radius:20px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.06)}"
        ".art svg{width:100%;height:auto;display:block}figcaption{margin-top:8px;text-align:center}"
        f"</style><div class=g>{cards}</div>")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
