# Review: Samarth Saathi product film (2:28)

**Story** (13 scenes, one AI voice, en-IN-Neerja):
1. Hook on the Samarth homepage.
2. The Saathi section.
3. Plan and parent details.
4. Razorpay test checkout, then the Saathi code with the assigned care manager.
5. Welcome slides on the phone.
6. Setup that redeems the code.
7. The self-updating home screen.
8. The medicine reminder.
9. The daily call.
10. SOS.
11. The care manager's list, reasons, readings and medicines.
12. The family summary.
13. The closing card.

**Real screens:** every screen is a capture of the running product.
- **Phone setup:** done on the Motorola with the code issued by the hub (SAATHI-X4U52V, Kamla Devi, Lucknow → Rajesh Verma).
- **Medicine reminder:** the real alarm, ringing for the medicine her care manager added.
- **Call and SOS:** screens from the earlier capture (same person).

**Checked:**
- `hyperframes check`: no errors and no warnings. Labels are at least 28px; browser-bar text is marked as texture.
- **Snapshot review, two frames per scene:**
  - highlights land on the word that names them (plans, parent details, code, WhatsApp, the three feature cards, readings, medicines);
  - captions never overlap and stay in the title-safe area;
  - phone frames keep each screenshot's aspect ratio.
- **Fixed during review:**
  - feature-card highlight positions;
  - illustrations not loading (duplicate `xmlns` in the generated SVGs, now fixed at the source in `design/build_illustrations.py`).

**Known limits:**
- **Phone shots:** the SOS and call screens come from the earlier capture (older Aegis Saathi wording on the call screen).
- **Music:** the existing generated bed at volume 0.12, with no sound effects on actions.
- **Portal text:** the portal screens are dense, so the highlight and the push-in carry the point rather than the small text.
