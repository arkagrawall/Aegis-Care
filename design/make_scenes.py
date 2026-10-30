"""Writes the scene SVGs that are composed from shared pieces (blob shapes, floor, props).
The three sample scenes (welcome, calls, family) are hand-edited files and are not touched here.
python design/make_scenes.py"""
import os

S = os.path.join(os.path.dirname(os.path.abspath(__file__)), "illustrations", "scenes")
MINT, FLOOR, PALE = "#E3F3EE", "#9AD8C9", "#CFEDE5"
TEAL, TEAL2, DARK = "#0E7C6B", "#3FB59F", "#2F3A45"
BLOBS = {
    "a": "M52,108 C60,52 118,24 178,26 C240,28 302,46 318,104 C334,160 328,226 276,254 C226,280 136,284 88,258 C40,232 44,160 52,108Z",
    "b": "M60,96 C76,44 136,22 196,28 C258,34 312,64 316,124 C320,184 304,236 256,256 C204,278 126,280 86,252 C46,224 46,150 60,96Z",
    "c": "M46,118 C50,58 112,26 176,24 C244,22 306,54 318,114 C330,174 318,232 268,258 C218,284 132,286 86,260 C40,234 42,172 46,118Z",
}


def scene(name, note, blob, body, floor=True):
    fl = f'  <g clip="blob"><rect x="0" y="226" width="360" height="80" fill="{FLOOR}"/></g>\n' if floor else ""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 300">\n  <!-- {note} -->\n'
           f'  <path class="blob" id="blob" d="{BLOBS[blob]}" fill="{MINT}"/>\n{fl}{body}</svg>\n')
    open(os.path.join(S, name + ".svg"), "w", encoding="utf-8").write(svg)


def plant(x, y, s=1.0):
    return (f'  <g transform="translate({x} {y}) scale({s})">\n'
            f'    <path d="M-14,0 L14,0 L10,26 L-10,26Z" fill="#E08A5A"/><path d="M-14,0 L14,0 L13,6 L-13,6Z" fill="#C97447"/>\n'
            f'    <ellipse cx="-8" cy="-26" rx="7" ry="20" fill="#2E9C88" transform="rotate(-22 -8 -26)"/>\n'
            f'    <ellipse cx="8" cy="-28" rx="7" ry="22" fill="{TEAL}" transform="rotate(18 8 -28)"/>\n'
            f'    <ellipse cx="0" cy="-34" rx="6.5" ry="24" fill="{TEAL2}"/>\n  </g>\n')


def sparkle(x, y, c="#F29B4B", s=1.0):
    return f'  <path transform="translate({x} {y}) scale({s})" d="M0,-11 l3,8 l8,3 l-8,3 l-3,8 l-3,-8 l-8,-3 l8,-3z" fill="{c}"/>\n'


def heart(x, y, s=1.0, c="#F07862"):
    return f'  <path transform="translate({x} {y}) scale({s})" d="M0,-4 c-4,-6 -14,-3 -12,5 c1.5,5 12,12 12,12 c0,0 10.5,-7 12,-12 c2,-8 -8,-11 -12,-5z" fill="{c}"/>\n'


def check_badge(x, y, r=26):
    return (f'  <circle cx="{x}" cy="{y}" r="{r}" fill="#2D8A4E"/>\n'
            f'  <path d="M{x - r * .42},{y + r * .02} L{x - r * .1},{y + r * .32} L{x + r * .45},{y - r * .3}" fill="none" stroke="#FFFFFF" stroke-width="{r * .2:.1f}" stroke-linecap="round" stroke-linejoin="round"/>\n')


def face(cx, cy, r, bg, mood):
    eyes = f'<circle cx="{cx - r * .35}" cy="{cy - r * .2}" r="{r * .12:.1f}" fill="#FFFFFF"/><circle cx="{cx + r * .35}" cy="{cy - r * .2}" r="{r * .12:.1f}" fill="#FFFFFF"/>'
    mouth = {"good": f'M{cx - r * .42},{cy + r * .2} q{r * .42},{r * .4} {r * .84},0',
             "ok": f'M{cx - r * .38},{cy + r * .32} l{r * .76},0',
             "bad": f'M{cx - r * .4},{cy + r * .45} q{r * .4},{-r * .38} {r * .8},0'}[mood]
    return (f'    <circle cx="{cx}" cy="{cy}" r="{r}" fill="{bg}"/>{eyes}\n'
            f'    <path d="{mouth}" fill="none" stroke="#FFFFFF" stroke-width="{r * .14:.1f}" stroke-linecap="round"/>\n')


# 2. Daily check-in: dadi points at a big phone with three faces
rows = ""
for i, (bg, fc, mood) in enumerate((("#E3F4E9", "#2D8A4E", "good"), ("#FBF0D9", "#D4A915", "ok"), ("#FBE4E1", "#C2392F", "bad"))):
    y = 78 + i * 50
    rows += f'    <rect x="210" y="{y}" width="82" height="40" rx="10" fill="{bg}"/>\n' + face(231, y + 20, 12, fc, mood)
    rows += f'    <rect x="250" y="{y + 13}" width="32" height="5" rx="2.5" fill="#FFFFFF"/><rect x="250" y="{y + 23}" width="22" height="5" rx="2.5" fill="#FFFFFF"/>\n'
scene("checkin", "Slide 2: Dadi taps how she feels on a big, friendly phone screen.", "a",
      f'  <rect x="198" y="48" width="108" height="194" rx="18" fill="{DARK}"/>\n'
      f'  <rect x="205" y="60" width="94" height="170" rx="11" fill="#FFFFFF"/>\n{rows}'
      f'  <circle cx="231" cy="98" r="19" fill="none" stroke="#2D8A4E" stroke-width="2.4" opacity="0.45"/>\n'
      f'  <circle cx="231" cy="98" r="25" fill="none" stroke="#2D8A4E" stroke-width="2" opacity="0.2"/>\n'
      + sparkle(176, 52, "#F29B4B", .8) +
      '  <use-part name="dadi_point" transform="translate(62 22)"/>\n')

# 4. Medicines on time: alarm clock, a week pill box, a big tick
pills = ""
for i in range(7):
    x = 86 + i * 27
    lid = TEAL2 if i % 2 == 0 else "#9AD8C9"
    pills += (f'  <rect x="{x}" y="186" width="23" height="40" rx="5" fill="#FFFFFF"/>\n'
              f'  <rect x="{x}" y="186" width="23" height="9" rx="4" fill="{lid}"/>\n')
    if i < 5:
        pills += f'  <ellipse cx="{x + 11.5}" cy="{212}" rx="6" ry="3.6" fill="#F07862" transform="rotate(-20 {x + 11.5} 212)"/>\n'
scene("medicines", "Slide 4: an alarm clock rings, the week's pill box, and a big tick - medicines on time.", "b",
      f'  <rect x="78" y="178" width="204" height="56" rx="12" fill="#B7E4D8"/>\n{pills}'
      '  <circle cx="96" cy="66" r="9" fill="#E08A5A"/><circle cx="148" cy="66" r="9" fill="#E08A5A"/>\n'
      '  <circle cx="122" cy="108" r="44" fill="#F29B4B"/>\n  <circle cx="122" cy="108" r="35" fill="#FFFFFF"/>\n'
      '  <path d="M122,108 L122,84 M122,108 L139,116" fill="none" stroke="#2F3A45" stroke-width="4" stroke-linecap="round"/>\n'
      '  <circle cx="122" cy="108" r="4" fill="#B1423D"/>\n'
      '  <path d="M68,84 q-8,8 -6,20 M60,76 q-12,14 -8,32 M176,84 q8,8 6,20 M184,76 q12,14 8,32" fill="none" stroke="#F29B4B" stroke-width="3" stroke-linecap="round"/>\n'
      + check_badge(262, 104, 34) +
      '  <rect x="236" y="148" width="14" height="30" rx="7" fill="#3FB59F" transform="rotate(35 243 163)"/>\n'
      '  <rect x="236" y="148" width="14" height="15" rx="7" fill="#FFFFFF" transform="rotate(35 243 163)"/>\n'
      + sparkle(206, 58, "#F07862", .7), floor=False)

# 5. Help with one press: a wrist with a watch reaching for a big SOS button
scene("sos", "Slide 5: a hand with a smartwatch reaches for the big red SOS button.", "c",
      '  <circle cx="218" cy="128" r="72" fill="#F9D5D2"/>\n  <circle cx="218" cy="128" r="56" fill="#F1A7A0"/>\n'
      '  <circle cx="222" cy="133" r="42" fill="#B3261E"/>\n  <circle cx="218" cy="128" r="42" fill="#D93025"/>\n'
      '  <g fill="none" stroke="#FFFFFF" stroke-width="4.6" stroke-linecap="round" stroke-linejoin="round">\n'
      '    <path d="M199,118 c0,-5 -11,-5 -11,1 c0,6 11,5 11,11 c0,6 -11,6 -11,1"/>\n'
      '    <ellipse cx="218" cy="125" rx="6" ry="9"/>\n'
      '    <path d="M247,118 c0,-5 -11,-5 -11,1 c0,6 11,5 11,11 c0,6 -11,6 -11,1"/>\n  </g>\n'
      '  <g clip="blob">\n'
      '  <path d="M40,300 C70,260 104,226 140,200 L160,224 C126,248 96,276 76,300Z" fill="#C98B62"/>\n'
      '  <path d="M140,200 C150,194 162,190 170,192 C178,194 180,202 176,208 L160,224Z" fill="#C98B62"/>\n'
      '  <path d="M150,196 C160,186 170,180 176,184 C180,188 176,194 170,198Z" fill="#AD7350"/>\n'
      '  <path d="M96,234 L118,214 L138,238 L116,258Z" fill="#2F3A45"/>\n'
      '  <rect x="104" y="222" width="26" height="26" rx="6" fill="#2F3A45" transform="rotate(-42 117 235)"/>\n'
      '  <rect x="108" y="226" width="18" height="18" rx="4" fill="#0E7C6B" transform="rotate(-42 117 235)"/>\n'
      + heart(117, 233, .32, "#FFFFFF") + '  </g>\n' + sparkle(296, 60, "#F29B4B", .8), floor=False)

# 7. Language: "अ" and "A" in two speech bubbles
scene("language", "Setup step: choose your language - two speech bubbles, Hindi and English.", "a",
      '  <g transform="rotate(-6 132 120)">\n'
      '    <rect x="72" y="70" width="120" height="100" rx="24" fill="#F29B4B"/>\n    <path d="M100,166 L92,192 L122,168Z" fill="#F29B4B"/>\n'
      '    <g fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">\n'
      '      <path d="M100,96 L166,96"/><path d="M148,96 L148,150"/><path d="M128,124 L148,124"/>\n'
      '      <path d="M108,108 C116,102 128,106 126,114 C124,121 116,122 112,121 C124,120 130,128 126,137 C122,145 110,145 104,139"/>\n'
      '    </g>\n  </g>\n'
      '  <g transform="rotate(5 236 160)">\n'
      '    <rect x="180" y="112" width="112" height="96" rx="24" fill="#0E7C6B"/>\n    <path d="M262,204 L276,228 L244,206Z" fill="#0E7C6B"/>\n'
      '    <path d="M218,186 L236,134 L254,186 M224,170 L248,170" fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>\n'
      '  </g>\n' + heart(296, 82, .9) + sparkle(70, 210, "#3FB59F", .8) + sparkle(296, 236, "#F07862", .6), floor=False)

# 8. Name and age: dadaji shows his ID card
scene("name", "Setup step: your name and age - dadaji shows his ID card.", "b",
      plant(84, 226, .9) + sparkle(268, 74, "#F29B4B", .8) +
      '  <use-part name="dadaji_card" transform="translate(126 20)"/>\n')

# 9. Care manager: she holds her clipboard, a call bubble beside her
scene("care", "Setup step: your care manager - she holds her clipboard; a call bubble beside her.", "c",
      '  <path d="M218,60 L290,60 C299,60 304,65 304,74 L304,108 C304,117 299,122 290,122 L246,122 L232,138 L233,122 L218,122 C209,122 204,117 204,108 L204,74 C204,65 209,60 218,60Z" fill="#FFFFFF"/>\n'
      '  <path d="M240,78 c-3,0 -6,3 -6,6 c0,12 10,22 22,22 c3,0 6,-3 6,-6 l0,-5 l-8,-3 l-3,4 c-5,-2 -9,-6 -11,-11 l4,-3 l-3,-8z" fill="#0E7C6B"/>\n'
      '  <path d="M266,80 q8,4 8,14 M266,72 q14,6 14,22" fill="none" stroke="#3FB59F" stroke-width="3" stroke-linecap="round"/>\n'
      + plant(282, 232, .8) + '  <use-part name="care_manager" transform="translate(96 22)"/>\n')

# 10. Permissions: a shield with the microphone, bell and location badges
scene("permissions", "Setup step: permissions - a shield surrounded by the microphone, bell and location badges.", "a",
      '  <path d="M180,62 L236,84 L236,140 C236,184 210,214 180,230 C150,214 124,184 124,140 L124,84Z" fill="#0E7C6B"/>\n'
      '  <path d="M180,62 L236,84 L236,140 C236,184 210,214 180,230Z" fill="#0A5F52"/>\n'
      '  <path d="M156,146 L174,164 L206,126" fill="none" stroke="#FFFFFF" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>\n'
      '  <circle cx="96" cy="98" r="28" fill="#FFFFFF"/>\n  <rect x="89" y="82" width="14" height="24" rx="7" fill="#F29B4B"/>\n'
      '  <path d="M83,98 a13,13 0 0 0 26,0 M96,111 L96,118" fill="none" stroke="#F29B4B" stroke-width="3" stroke-linecap="round"/>\n'
      '  <circle cx="268" cy="96" r="28" fill="#FFFFFF"/>\n'
      '  <path d="M256,104 L280,104 C276,100 276,96 276,90 C276,84 272,80 268,80 C264,80 260,84 260,90 C260,96 260,100 256,104Z" fill="#F07862"/>\n'
      '  <circle cx="268" cy="108" r="3.4" fill="#F07862"/>\n'
      '  <circle cx="262" cy="200" r="28" fill="#FFFFFF"/>\n'
      '  <path d="M262,216 C256,208 250,201 250,193 C250,186 255,181 262,181 C269,181 274,186 274,193 C274,201 268,208 262,216Z" fill="#3F5BA9"/>\n'
      '  <circle cx="262" cy="193" r="4.4" fill="#FFFFFF"/>\n' + sparkle(92, 196, "#3FB59F", .8), floor=False)

# 11. No medicines yet: an empty pill box with a plus
cells = "".join(f'  <rect x="{104 + i * 22}" y="150" width="18" height="40" rx="4" fill="#FFFFFF"/>\n' for i in range(7))
scene("meds_empty", "Empty state: no medicines yet - an open, empty pill box and a plus.", "b",
      '  <rect x="96" y="140" width="168" height="58" rx="12" fill="#B7E4D8"/>\n' + cells +
      '  <path d="M96,140 L264,140 L250,104 L110,104Z" fill="#9AD8C9"/>\n'
      '  <circle cx="256" cy="98" r="24" fill="#0E7C6B"/>\n  <path d="M256,86 L256,110 M244,98 L268,98" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>\n'
      + sparkle(110, 80, "#F29B4B", .7), floor=False)

# 12. No family numbers yet: a phone book with a heart and a handset
scene("contacts_empty", "Empty state: no family numbers yet - a phone book with a heart, and a handset.", "c",
      '  <rect x="118" y="70" width="112" height="150" rx="12" fill="#F07862"/>\n  <rect x="118" y="70" width="20" height="150" rx="8" fill="#D9614E"/>\n'
      '  <rect x="150" y="96" width="62" height="42" rx="8" fill="#FFFFFF"/>\n' + heart(181, 115, .9) +
      '  <rect x="152" y="152" width="56" height="6" rx="3" fill="#FFFFFF" opacity="0.7"/><rect x="152" y="166" width="40" height="6" rx="3" fill="#FFFFFF" opacity="0.7"/>\n'
      '  <circle cx="250" cy="196" r="28" fill="#0E7C6B"/>\n'
      '  <path d="M240,184 c-3,0 -6,3 -6,6 c0,12 10,22 22,22 c3,0 6,-3 6,-6 l0,-5 l-8,-3 l-3,4 c-5,-2 -9,-6 -11,-11 l4,-3 l-3,-8z" fill="#FFFFFF"/>\n'
      + sparkle(96, 96, "#F29B4B", .7), floor=False)

# 13. Watch not connected: a smartwatch looking for its phone
scene("watch_empty", "Empty state: watch not connected - a smartwatch sending Bluetooth waves.", "a",
      '  <rect x="152" y="40" width="56" height="70" rx="12" fill="#2F3A45"/>\n  <rect x="152" y="190" width="56" height="70" rx="12" fill="#2F3A45"/>\n'
      '  <rect x="136" y="96" width="88" height="108" rx="24" fill="#3B4754"/>\n  <rect x="146" y="106" width="68" height="88" rx="16" fill="#0E7C6B"/>\n'
      '  <path d="M170,134 L192,154 L181,164 L181,124 L192,134 L170,154" fill="none" stroke="#FFFFFF" stroke-width="4.6" stroke-linecap="round" stroke-linejoin="round"/>\n'
      '  <path d="M246,120 q14,30 0,60 M262,106 q24,44 0,88 M114,120 q-14,30 0,60 M98,106 q-24,44 0,88" fill="none" stroke="#3FB59F" stroke-width="5" stroke-linecap="round"/>\n'
      '  <rect x="224" y="138" width="8" height="22" rx="3" fill="#3B4754"/>\n', floor=False)

# 14. All done for today: dadi relaxes with chai, a big tick
scene("all_done", "Empty state: all done today - dadi relaxes with a cup of chai; a big tick.", "c",
      check_badge(262, 86, 30) + plant(86, 228, .85) + heart(282, 150, .7) +
      '  <use-part name="dadi_tea" transform="translate(124 22)"/>\n')

# 15. Web sign-in: the care manager at her desk, a short list on the screen
rows = "".join(f'  <circle cx="{214}" cy="{y}" r="5" fill="{c}"/><rect x="226" y="{y - 3}" width="{w}" height="6" rx="3" fill="#C9CED0"/>\n'
               for y, c, w in ((108, "#A8201A", 48), (126, "#E0651C", 38), (144, "#D4A915", 44), (162, "#2D8A4E", 30)))
scene("desk", "Web sign-in: the care manager at her desk; the screen shows a short list, most urgent first.", "b",
      '  <rect x="196" y="88" width="104" height="92" rx="10" fill="#2F3A45"/>\n  <rect x="202" y="94" width="92" height="80" rx="6" fill="#FFFFFF"/>\n' + rows +
      '  <rect x="240" y="180" width="14" height="22" fill="#3B4754"/>\n  <rect x="224" y="198" width="46" height="8" rx="4" fill="#3B4754"/>\n'
      '  <use-part name="care_manager" transform="translate(74 22)"/>\n'
      '  <rect x="48" y="200" width="270" height="14" rx="6" fill="#C97447"/>\n  <rect x="58" y="214" width="250" height="48" fill="#B0623A"/>\n'
      '  <rect x="58" y="214" width="250" height="6" fill="#9A5532"/>\n'
      '  <path d="M118,192 L136,192 L134,200 L120,200Z" fill="#FFFFFF"/>\n' + plant(298, 200, .6))

# 16. Family page: the daughter reads an update on her phone, a heart floats up
scene("family_phone", "Family page: the daughter reads a weekly update on her phone; a heart floats up.", "a",
      '  <path d="M208,58 L284,58 C293,58 298,63 298,72 L298,112 C298,121 293,126 284,126 L232,126 L218,142 L220,126 L208,126 C199,126 194,121 194,112 L194,72 C194,63 199,58 208,58Z" fill="#FFFFFF"/>\n'
      + heart(246, 90, 1.2) + '  <rect x="212" y="110" width="40" height="5" rx="2.5" fill="#C9CED0"/>\n'
      + plant(272, 230, .85) + sparkle(96, 70, "#F29B4B", .8) +
      '  <use-part name="daughter_phone" transform="translate(96 22)"/>\n')

# 17. No match (portal search): a magnifier over three person cards
cards = ""
for i, (y, c) in enumerate(((84, "#9AD8C9"), (132, "#F9D5D2"), (180, "#FBF0D9"))):
    cards += (f'  <rect x="96" y="{y}" width="150" height="38" rx="10" fill="#FFFFFF"/>\n  <circle cx="117" cy="{y + 19}" r="11" fill="{c}"/>\n'
              f'  <rect x="136" y="{y + 11}" width="70" height="6" rx="3" fill="#C9CED0"/><rect x="136" y="{y + 22}" width="46" height="6" rx="3" fill="#E1E8E5"/>\n')
scene("search_empty", "Portal: nobody matches - a magnifier over three person cards.", "c",
      cards + '  <circle cx="238" cy="156" r="36" fill="#FFFFFF" opacity="0.6"/>\n'
      '  <circle cx="238" cy="156" r="36" fill="none" stroke="#0E7C6B" stroke-width="10"/>\n'
      '  <path d="M264,182 L292,210" fill="none" stroke="#0E7C6B" stroke-width="14" stroke-linecap="round"/>\n', floor=False)
print("scenes written")
