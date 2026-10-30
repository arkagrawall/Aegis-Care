"""Screenshots design/illustrations/sheet.html (or one built scene) with headless Chrome, for review.
python design/render.py [scene] [out.png]"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
scene = sys.argv[1] if len(sys.argv) > 1 else None
out = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "design", "illustrations", "build", (scene or "sheet") + ".png"))
if scene:
    src = os.path.join(ROOT, "design", "illustrations", "build", scene + ".svg")
    page = os.path.join(ROOT, "design", "illustrations", "build", "_one.html")
    open(page, "w", encoding="utf-8").write(
        "<!doctype html><body style='margin:0;background:#fff'>" + open(src, encoding="utf-8").read().replace("<svg ", "<svg width='720' height='600' ", 1))
    size = "720,600"
else:
    page = os.path.join(ROOT, "design", "illustrations", "sheet.html")
    size = "1400,1300"
subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", f"--window-size={size}", f"--screenshot={out}", "file:///" + page.replace("\\", "/")],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
print(out)
