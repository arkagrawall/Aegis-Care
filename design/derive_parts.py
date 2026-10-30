"""Makes the extra poses from the base characters by swapping their arm shapes, so faces, clothes and
colours stay identical across scenes. Run after editing a base part:  python design/derive_parts.py"""
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "illustrations", "parts")


def read(n):
    return open(os.path.join(P, n + ".svg"), encoding="utf-8").read()


def cut(s, start, end, new):
    a, b = s.index(start), s.index(end)
    return s[:a] + new + s[b:]


def write(n, s):
    open(os.path.join(P, n + ".svg"), "w", encoding="utf-8").write(s)


# Dadi pointing at something to her side (checking in on a big phone)
s = read("dadi_wave")
s = s.replace("Waving with her right hand (our right), phone in her left.", "Pointing with her right hand (our right) at something beside her.")
s = cut(s, "  <!-- right arm, waving (behind the body) -->", "  <!-- neck -->", """  <!-- right arm, pointing forward -->
  <path d="M77,92 L85,88 C93,92 101,96 109,98 L107,106 C98,104 89,101 79,100Z" fill="#AD7350"/>
  <ellipse cx="110.5" cy="102" rx="6" ry="5.4" fill="#C98B62"/>
  <path d="M114,99.5 L121,96.5" fill="none" stroke="#C98B62" stroke-width="3.6" stroke-linecap="round"/>
""")
s = cut(s, "  <!-- left arm with phone -->", "  <!-- feet -->", """  <!-- left arm down -->
  <path d="M34,94 L43,95 C44,107 44,117 44,125 L36,125 C35,115 34,104 34,94Z" fill="#C98B62"/>
  <ellipse cx="40" cy="128" rx="5.2" ry="5.2" fill="#C98B62"/>
""")
write("dadi_point", s)

# Dadi with a cup of chai
s = read("dadi_walk")
s = s.replace("Walking arm in arm: her right arm hangs down, her left arm is held by the person beside her (drawn by that part).",
              "Holding a cup of chai at her chest, relaxed.")
s = cut(s, "  <!-- right arm down -->", "  <!-- feet -->", """  <!-- right arm bent, holding a cup -->
  <path d="M78,92 L86,91 C89,100 87,109 81,116 L74,111 C78,105 79,99 78,92Z" fill="#AD7350"/>
  <path d="M63,104 L77,104 L75.5,118 L64.5,118Z" fill="#FFFFFF"/>
  <path d="M63,104 L77,104 L76.6,107.5 L63.4,107.5Z" fill="#E8B04B"/>
  <path d="M65,98 c-2.4,-3 2.4,-4.6 0,-8 M71,98 c-2.4,-3 2.4,-4.6 0,-8" fill="none" stroke="#9AD8C9" stroke-width="1.8" stroke-linecap="round"/>
  <ellipse cx="76" cy="114" rx="5.2" ry="5" fill="#C98B62"/>
""")
write("dadi_tea", s)

# Dadaji showing his ID card
s = read("dadaji_phone")
s = s.replace("Phone held to his ear with his left hand (our right), walking stick in the other.",
              "Showing an ID card with his photo in his left hand (our right), walking stick in the other.")
s = cut(s, "  <!-- right arm up to the ear, holding the phone -->", "  <!-- head -->", """  <!-- right arm bent, holding the ID card in front -->
  <path d="M77,79 C84,86 88,98 89,108 L81,110 L74,88Z" fill="#344C8F"/>
  <g transform="rotate(-6 80 104)">
    <rect x="61" y="90" width="38" height="26" rx="3.5" fill="#FFFFFF"/>
    <rect x="61" y="90" width="38" height="6" rx="3" fill="#0E7C6B"/>
    <rect x="65" y="99" width="10" height="13" rx="2" fill="#CFEDE5"/>
    <circle cx="70" cy="104" r="2.6" fill="#E2A57E"/>
    <path d="M66,112 c1,-3 7,-3 8,0z" fill="#3F5BA9"/>
    <rect x="78" y="101" width="16" height="2.4" rx="1.2" fill="#C9CED0"/>
    <rect x="78" y="106" width="12" height="2.4" rx="1.2" fill="#C9CED0"/>
  </g>
  <path d="M89,104 C84,110 79,114 73,117 L70,111 C75,108 80,104 82,99Z" fill="#E2A57E"/>
  <ellipse cx="71" cy="115" rx="5.4" ry="5" fill="#E2A57E"/>
""")
write("dadaji_card", s)

# Daughter looking at her phone
s = read("daughter_walk")
s = s.replace("Her right arm (our right) reaches out to hold the arm of whoever walks beside her.",
              "Holding her phone in front of her chest with her right hand (our right).")
s = cut(s, "  <!-- right arm reaching across -->", "  <!-- head -->", """  <!-- right arm bent, phone in hand -->
  <path d="M76,78 C84,86 88,98 89,106 L81,108 C80,100 78,93 72,88Z" fill="#D9614E"/>
  <path d="M89,104 C84,104 79,102 74,99 L77,93 C81,96 85,97 88,98Z" fill="#C98B62"/>
  <g transform="rotate(-12 70 90)">
    <rect x="63" y="77" width="13" height="23" rx="2.6" fill="#2F3A45"/>
    <rect x="64.8" y="79.6" width="9.4" height="17" rx="1.4" fill="#9FE0D2"/>
  </g>
  <ellipse cx="74.5" cy="96" rx="5" ry="5" fill="#C98B62"/>
""")
write("daughter_phone", s)
print("derived: dadi_point, dadi_tea, dadaji_card, daughter_phone")
