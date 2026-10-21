#!/usr/bin/env python3
"""Narration (Amazon Polly, Matthew, generative), timeline, and the soundtrack mix.

  python3 audio.py     -> audio/sNN.mp3, timeline.json, audio/mix.wav

Re-running only re-synthesizes scenes whose text changed (text hash in timeline.json).
Music and click sounds are generated here (numpy), so there is nothing third-party in the mix.
"""
import hashlib
import json
import subprocess
import sys
import wave

import numpy as np

import common as C

SR = 44100


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def synth(text, out):
    r = subprocess.run(["aws", "polly", "synthesize-speech", "--engine", C.ENGINE, "--voice-id", C.VOICE,
                        "--output-format", "mp3", "--text", text, "--profile", "claude-kng",
                        "--region", "us-east-1", str(out)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("polly failed: " + r.stderr[:300])


def narrate():
    C.AUDIO.mkdir(parents=True, exist_ok=True)
    old = {}
    if C.TIMELINE.exists():
        old = {s["name"]: s for s in json.loads(C.TIMELINE.read_text())["scenes"]}
    scenes, t = [], 0.0
    for i, (name, planned, text) in enumerate(C.SCENES):
        mp3 = C.AUDIO / f"s{i + 1:02d}.mp3"
        h = hashlib.sha1(text.encode()).hexdigest()
        if not (mp3.exists() and old.get(name, {}).get("hash") == h):
            synth(text, mp3)
        nd = round(duration(mp3), 2)
        dur = round(max(planned, C.NARRATION_DELAY + nd + C.SCENE_TAIL), 2)
        scenes.append({"name": name, "text": text, "hash": h, "start": round(t, 2), "dur": dur,
                       "narr_start": round(t + C.NARRATION_DELAY, 2), "narr_dur": nd, "mp3": str(mp3)})
        t += dur
    tl = {"total": round(t, 2), "scenes": scenes}
    C.TIMELINE.write_text(json.dumps(tl, indent=1))
    return tl


def tone(freq, dur, amp=1.0, attack=0.05, release=0.3, harmonics=(1.0, 0.35, 0.12)):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = sum(h * np.sin(2 * np.pi * freq * (k + 1) * t) for k, h in enumerate(harmonics))
    env = np.minimum(1.0, t / attack) * np.minimum(1.0, (dur - t) / release)
    return amp * y * np.clip(env, 0, 1) / sum(harmonics)


def add(buf, sig, at):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[:j - i]


def click(at, buf):
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(int(at * 1000))
    sig = (rng.standard_normal(n) * 0.25 + np.sin(2 * np.pi * 880 * t) * 0.5) * np.exp(-t * 55)
    add(buf, sig * 0.5, at)


def music(total):
    buf = np.zeros(int((total + 1) * SR))
    chords = [(220.00, 261.63, 329.63), (174.61, 220.00, 261.63), (261.63, 329.63, 392.00), (196.00, 246.94, 293.66)]
    step = 8.0
    for i in range(int(total / step) + 2):
        for f in chords[i % 4]:
            add(buf, tone(f, step + 1.5, 0.11, attack=1.6, release=2.0), i * step)
    pent = [440.0, 523.25, 587.33, 659.25, 783.99]
    rng = np.random.default_rng(7)
    at = 3.0
    while at < total - 3:
        add(buf, tone(float(rng.choice(pent)), 1.6, 0.07, attack=0.01, release=1.4, harmonics=(1.0, 0.2)), at)
        at += float(rng.choice([2.0, 3.0, 4.0]))
    return buf


def mix(tl):
    total = tl["total"]
    m = music(total) * 0.9
    sfx = np.zeros_like(m)
    for name, (sc, off) in C.SNAPS.items():
        click(C.abs_time(tl, sc, off), sfx)
    click(C.abs_time(tl, *C.SERVER_SETTLE), sfx)
    # final organ swell (self-created low stacked tones), and three quiet organ notes in the instrument scene
    swell = C.abs_time(tl, *C.FINAL_SWELL)
    for f in (130.81, 196.00, 261.63, 329.63):
        add(sfx, tone(f, 4.2, 0.16, attack=1.2, release=1.8, harmonics=(1.0, 0.6, 0.35, 0.2)), swell)
    inst = C.abs_time(tl, 4, 7.0)
    for k, f in enumerate((261.63, 329.63, 392.00)):
        add(sfx, tone(f, 1.4, 0.12, attack=0.04, release=0.9, harmonics=(1.0, 0.7, 0.4, 0.2)), inst + k * 0.55)
    sig = m + sfx
    # fade in / out
    n = len(sig)
    sig[:SR * 2] *= np.linspace(0, 1, SR * 2)
    tail = int(2.5 * SR)
    end = int(total * SR)
    sig = sig[:end + tail]
    sig[end - tail:end] *= np.linspace(1, 0.0, tail)
    sig[end:] = 0
    peak = np.max(np.abs(sig)) or 1
    sig = sig / peak * 0.22                      # quiet bed under the narration
    pcm = (np.clip(sig, -1, 1) * 32767).astype("<i2")
    path = C.AUDIO / "bed.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    # narration placed on the timeline, then mixed with the bed
    inputs, filt = ["-i", str(path)], ["[0:a]volume=1.0[bed]"]
    labels = ["[bed]"]
    for i, s in enumerate(tl["scenes"]):
        inputs += ["-i", s["mp3"]]
        ms = int(s["narr_start"] * 1000)
        filt.append(f"[{i + 1}:a]adelay={ms}|{ms},volume=1.6[n{i}]")
        labels.append(f"[n{i}]")
    filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,alimiter=limit=0.95[out]")
    out = C.AUDIO / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "[out]", "-t", str(total), "-ar", "44100", str(out)], check=True)
    return out


if __name__ == "__main__":
    tl = narrate()
    for s in tl["scenes"]:
        print(f"{s['name']:11s} start {s['start']:6.2f}  dur {s['dur']:5.2f}  narration {s['narr_dur']:5.2f}s")
    print("total", tl["total"])
    print(mix(tl))
