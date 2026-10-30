"""
Downloads the two small Vosk speech models the voice agent needs (Hindi and Indian English).
They are not committed to git (about 130 MB unpacked). Run once:   python download_models.py

  vosk-model-small-hi-0.22     Hindi, 42 MB      Apache 2.0   https://alphacephei.com/vosk/models
  vosk-model-small-en-in-0.4   Indian English, 36 MB   Apache 2.0
"""
import io
import os
import urllib.request
import zipfile

MODELS = {
    "vosk-model-small-hi-0.22": "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip",
    "vosk-model-small-en-in-0.4": "https://alphacephei.com/vosk/models/vosk-model-small-en-in-0.4.zip",
}
TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


def main() -> None:
    os.makedirs(TARGET, exist_ok=True)
    for name, url in MODELS.items():
        if os.path.isdir(os.path.join(TARGET, name)):
            print(f"[skip] {name} already present")
            continue
        print(f"[download] {name} ...")
        with urllib.request.urlopen(url) as r:
            data = r.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(TARGET)
        print(f"[ok] {name}")


if __name__ == "__main__":
    main()
