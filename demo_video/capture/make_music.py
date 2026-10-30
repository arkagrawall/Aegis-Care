"""Local background music with MusicGen (facebook/musicgen-small, CPU): one ~28 s seed clip, then a crossfaded
loop up to the film's length. Run with the musicgen venv:
  D:/Deviathon/tools/musicgen-venv/Scripts/python make_music.py [seconds]
-> ../assets/music/seed.wav and ../assets/music/bed.wav"""
import os, sys
import numpy as np
import soundfile as sf
import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "music")
os.makedirs(OUT, exist_ok=True)
TARGET = float(sys.argv[1]) if len(sys.argv) > 1 else 256.0
PROMPT = ("calm warm cinematic underscore for a healthcare product film, soft felt piano melody, gentle sustained strings, "
          "airy ambient pads, hopeful and reassuring, slow 84 bpm, major key, no drums, no vocals, clean mix")

torch.manual_seed(7)
proc = AutoProcessor.from_pretrained("facebook/musicgen-small")
model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")
sr = model.config.audio_encoder.sampling_rate
inputs = proc(text=[PROMPT], padding=True, return_tensors="pt")
with torch.no_grad():
    audio = model.generate(**inputs, do_sample=True, guidance_scale=3.0, max_new_tokens=1400)   # ~28 s at 50 tokens/s
seed = audio[0, 0].cpu().numpy().astype(np.float32)
seed = seed / max(1e-6, np.abs(seed).max()) * 0.85
sf.write(os.path.join(OUT, "seed.wav"), seed, sr)

# crossfade-loop the seed (skip its first and last half second, which often click)
clip = seed[int(0.5 * sr): len(seed) - int(0.5 * sr)]
xf = int(3.0 * sr)
fade_in, fade_out = np.linspace(0, 1, xf, dtype=np.float32), np.linspace(1, 0, xf, dtype=np.float32)
bed = clip.copy()
while len(bed) < TARGET * sr:
    bed = np.concatenate([bed[:-xf], bed[-xf:] * fade_out + clip[:xf] * fade_in, clip[xf:]])
bed = bed[: int(TARGET * sr)]
sf.write(os.path.join(OUT, "bed.wav"), bed, sr)
print("seed", round(len(seed) / sr, 1), "s; bed", round(len(bed) / sr, 1), "s @", sr, "Hz")
