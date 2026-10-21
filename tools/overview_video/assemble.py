#!/usr/bin/env python3
"""Assemble the finished video from frames/ and audio/mix.wav.

  python3 assemble.py   -> final/every-piece-in-place.mp4, .webm, .vtt, -transcript.txt, -poster.jpg

Captions are burned into the frames (render.py) and also written as a separate WebVTT file.
"""
import subprocess

from PIL import Image

import common as C
from render import captions

NAME = "every-piece-in-place"


def ts(x):
    h, rem = divmod(x, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def main():
    tl = C.load_timeline()
    C.FINAL.mkdir(parents=True, exist_ok=True)
    frames = C.WORK / "frames" / "f%05d.png"
    mix = C.AUDIO / "mix.wav"
    mp4 = C.FINAL / f"{NAME}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(C.FPS), "-i", str(frames), "-i", str(mix),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(mp4)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0",
                    "-c:a", "libopus", "-b:a", "128k", str(C.FINAL / f"{NAME}.webm")], check=True)
    cues = captions(tl)
    vtt = ["WEBVTT", ""]
    for i, (a, b, text) in enumerate(cues, 1):
        vtt += [str(i), f"{ts(a)} --> {ts(b)}", text, ""]
    (C.FINAL / f"{NAME}.vtt").write_text("\n".join(vtt))
    (C.FINAL / f"{NAME}-transcript.txt").write_text("\n\n".join(s["text"] for s in tl["scenes"]) + "\n")
    poster_t = tl["scenes"][6]["start"] + tl["scenes"][6]["dur"] - 0.3
    Image.open(C.WORK / "frames" / f"f{int(poster_t * C.FPS):05d}.png").convert("RGB").save(C.FINAL / f"{NAME}-poster.jpg", quality=90)
    print(mp4)


if __name__ == "__main__":
    main()
