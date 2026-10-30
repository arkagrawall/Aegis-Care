"""Lays the music bed under the rendered film: the voice ducks the music (sidechain), fades in and out,
loudness normalised for online playback (-14 LUFS, -1 dBTP). Video stream is copied, not re-encoded.
python mix_music.py <music file> [in.mp4] [out.mp4]"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(HERE, "..", "..", "tools", "ffmpeg.exe")
music = sys.argv[1]
src = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "renders", "aegis_saathi_demo_voice.mp4")
out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "..", "renders", "aegis_saathi_demo.mp4")

import av
with av.open(src) as c:
    total = float(c.duration / av.time_base)

graph = (
    f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.30,afade=t=in:d=2,afade=t=out:st={total - 4:.2f}:d=4[m];"
    "[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[v][key];"
    "[m][key]sidechaincompress=threshold=0.03:ratio=8:attack=40:release=600[duck];"
    "[v][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.87:level=false[a]"
)
subprocess.run([FF, "-y", "-i", src, "-stream_loop", "-1", "-i", music, "-filter_complex", graph,
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart", out], check=True)
print("wrote", out)
