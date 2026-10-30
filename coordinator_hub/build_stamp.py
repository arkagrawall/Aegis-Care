"""Fingerprint of the server code and portal files. Used by /api/health and by start.py to spot a stale running hub."""
import hashlib
import os


def build_stamp() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.md5()
    paths = [os.path.join(here, "server.py")]
    for sub in ("engine", "ai_agent", "static"):
        d = os.path.join(here, sub)
        if os.path.isdir(d):
            paths += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith((".py", ".js", ".css", ".html"))]
    for p in paths:
        try:
            with open(p, "rb") as f:
                h.update(f.read())
        except OSError:
            pass
    return h.hexdigest()[:10]
