"""
Aegis Saathi: one command to start everything.   python start.py

Starts the hub (python run.py) and a free Cloudflare quick tunnel, waits until the hub answers,
prints the public address to paste into the Android app (menu > Server settings), and saves it to
tunnel_url.txt. Ctrl+C stops both.

  python start.py            server + tunnel
  python start.py --local    server only (no tunnel)
  python start.py --restart  force a fresh hub even if one is running (a stale hub is restarted automatically)

Fixed address: set AEGIS_PUBLIC_URL=https://<your-name>.ngrok-free.app in coordinator_hub/.env and put
ngrok.exe in tools/ (once: tools\ngrok.exe config add-authtoken <token>). start.py then uses ngrok over
port 443 and the address never changes. Otherwise it falls back to a Cloudflare quick tunnel, which gets
a NEW address every start. cloudflared is looked for in tools/cloudflared.exe, then on PATH.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8000
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def hub_health():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=2) as r:
            return json.loads(r.read().decode()) if r.status == 200 else None
    except Exception:
        return None


def hub_up() -> bool:
    return hub_health() is not None


def local_build() -> str:
    sys.path.insert(0, os.path.join(ROOT, "coordinator_hub"))
    from build_stamp import build_stamp
    return build_stamp()


def kill_port(port: int) -> None:
    """Stops whatever listens on the port (the stale hub)."""
    if os.name == "nt":
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True).stdout
        pids = {ln.split()[-1] for ln in out.splitlines() if f":{port} " in ln and "LISTENING" in ln}
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/T", "/PID", pid], capture_output=True)
    else:
        subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)
    for _ in range(20):
        if not hub_up():
            return
        time.sleep(0.5)


def lan_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def find_cloudflared():
    local = os.path.join(ROOT, "tools", "cloudflared.exe")
    return local if os.path.exists(local) else shutil.which("cloudflared")


def find_ngrok():
    local = os.path.join(ROOT, "tools", "ngrok.exe")
    return local if os.path.exists(local) else shutil.which("ngrok")


def fixed_domain() -> str:
    """The ngrok static domain from AEGIS_PUBLIC_URL (environment or coordinator_hub/.env), without https://."""
    url = os.environ.get("AEGIS_PUBLIC_URL", "")
    if not url:
        try:
            with open(os.path.join(ROOT, "coordinator_hub", ".env"), encoding="utf-8") as f:
                for ln in f:
                    if ln.strip().startswith("AEGIS_PUBLIC_URL="):
                        url = ln.split("=", 1)[1].split("#")[0].strip().strip('"')
        except OSError:
            pass
    host = url.replace("https://", "").replace("http://", "").strip("/")
    return host if "ngrok" in host else ""


def announce(url: str) -> None:
    with open(os.path.join(ROOT, "tunnel_url.txt"), "w") as f:
        f.write(url + "\n")
    print("\n" + "=" * 64)
    print("  PUBLIC ADDRESS (paste into the Android app):")
    print("  " + url)
    print("  Website     : " + url + "/")
    print("  Care portal : " + url + "/portal")
    print("  Family view : " + url + "/family")
    print("  Phone sim   : " + url + "/phone")
    print("  (saved to tunnel_url.txt)   Ctrl+C to stop everything")
    print("=" * 64 + "\n")


def start_ngrok(exe: str, domain: str, procs: list) -> None:
    """Fixed address over port 443: the same URL every start, so Sarvam and the app never need re-pasting."""
    tun = subprocess.Popen([exe, "http", f"--url={domain}", str(PORT), "--log", "stdout", "--log-format", "logfmt"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    procs.append(tun)
    started = threading.Event()

    def pump():
        for line in tun.stdout:
            if "started tunnel" in line and not started.is_set():
                started.set()
                announce("https://" + domain)
            elif "lvl=eror" in line or "lvl=crit" in line or "ERR_NGROK" in line:
                m = re.search(r'err="?([^"]+)', line)
                print("[tunnel] ngrok: " + (m.group(1) if m else line.strip())[:300])

    threading.Thread(target=pump, daemon=True).start()
    if started.wait(30):
        print("[tunnel] connected: the fixed address works now")
    else:
        print("[tunnel] ngrok did not connect. If it says the authtoken is missing, run once:")
        print("         tools\\ngrok.exe config add-authtoken <your token from dashboard.ngrok.com>")


def main() -> int:
    local_only = "--local" in sys.argv
    restart = "--restart" in sys.argv
    procs = []
    try:
        h = hub_health()
        if h and not restart and h.get("build") == local_build():
            print(f"[hub] already running on port {PORT} with the current code, reusing it")
        else:
            if h:
                print("[hub] running copy is stale (or --restart given), stopping it...")
                kill_port(PORT)
            print("[hub] starting (first start trains the models, about a minute)...")
            hub = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py")], cwd=ROOT,
                                   env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
            procs.append(hub)
            while not hub_up():
                if hub.poll() is not None:
                    print("[hub] stopped unexpectedly, see the messages above")
                    return 1
                time.sleep(2)
            print(f"[hub] ready on http://localhost:{PORT}")
        llm = (hub_health() or {}).get("llm") or {}
        print("[ai]  Saathi talks with the Groq language model" if llm.get("on") else
              "[ai]  Saathi uses the built-in conversation (add GROQ_API_KEY to coordinator_hub/.env for the AI conversation)")
        ip = lan_ip()
        print(f"[lan] same Wi-Fi phone: http://{ip}:{PORT}   Android emulator: http://10.0.2.2:{PORT}   (fastest, never expires)" if ip else f"[lan] Android emulator: http://10.0.2.2:{PORT}")

        if local_only:
            print("Local only. Website: http://localhost:%d/   Care portal: http://localhost:%d/portal   Ctrl+C to stop." % (PORT, PORT))
        elif fixed_domain() and find_ngrok():
            start_ngrok(find_ngrok(), fixed_domain(), procs)
        else:
            if fixed_domain():
                print("[tunnel] AEGIS_PUBLIC_URL is an ngrok address but ngrok.exe is not in tools/ or on PATH; trying Cloudflare.")
            exe = find_cloudflared()
            if not exe:
                print("[tunnel] cloudflared not found. Put cloudflared.exe in tools/ or on PATH. Hub keeps running locally.")
            else:
                tun = subprocess.Popen(
                    [exe, "tunnel", "--url", f"http://localhost:{PORT}", "--no-autoupdate"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                )
                procs.append(tun)
                found = threading.Event()
                connected = threading.Event()
                blocked = threading.Event()

                def pump():
                    for line in tun.stdout:
                        if "Registered tunnel connection" in line:
                            connected.set()
                        if "port 7844" in line or "Failed to dial" in line:
                            blocked.set()
                        m = URL_RE.search(line)
                        if m and not found.is_set():
                            found.set()
                            announce(m.group(0))

                threading.Thread(target=pump, daemon=True).start()
                if not found.wait(60):
                    print("[tunnel] no address after 60 s. Check your internet connection and run again.")
                elif connected.wait(30):
                    print("[tunnel] connected: the public address works now")
                else:
                    # cloudflared hands out an address before it has a connection; without one, visitors get error 1033
                    print("[tunnel] NOT CONNECTED: the address above will show Cloudflare error 1033.")
                    if blocked.is_set():
                        print("         This network blocks outbound port 7844, which Cloudflare tunnels need.")
                    print("         Options: use the same-Wi-Fi / emulator address printed above (no tunnel needed),")
                    print("         connect Cloudflare WARP or a phone hotspot, then run: python start.py --restart")

        while True:
            time.sleep(1)
            for p in procs:
                if p.poll() is not None:
                    print("A process exited (code %s). Stopping." % p.returncode)
                    return 1
    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(5)
            except Exception:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())
