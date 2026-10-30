"""
Aegis Saathi - quickstart launcher.   python run.py

Starts the hub on http://localhost:8000 :
  /          care portal (coordinator and operations sign-in)
  /family    family view (sign in with the code a senior shares)
  /phone     browser phone simulator for testing the AI voice call without the Android app
"""

import os
import sys
import uvicorn

if __name__ == "__main__":
    hub_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coordinator_hub")
    os.chdir(hub_dir)
    sys.path.insert(0, hub_dir)

    print("=" * 72)
    print("   AEGIS SAATHI - EARLY WARNING FOR SENIORS LIVING AT HOME")
    print("=" * 72)
    print("First start trains and evaluates the models on the synthetic cohort (about a minute).")
    print("Speech models missing?  python coordinator_hub/download_models.py")
    print("-" * 72)
    print("  Care portal   http://localhost:8000/")
    print("  Family view   http://localhost:8000/family")
    print("  Phone sim     http://localhost:8000/phone")
    print("  Demo sign-ins http://localhost:8000/api/auth/demo   (hidden when AEGIS_DEMO_MODE=0)")
    print("=" * 72)

    from server import app
    uvicorn.run(app, host="0.0.0.0", port=8000)
