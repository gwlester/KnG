"""Shared script, schedule, and timeline for the "Every Piece in Place" overview video.

Source of truth for the words is Prompts/OverviewVideoStoryboard.md; keep NARRATION in sync with it.
Outputs go to WORK (outside any repo): ~/Videos/vcm-demo/overview/.
"""
import json
import os
from pathlib import Path

WORK = Path(os.environ.get("OVERVIEW_WORK", Path.home() / "Videos" / "vcm-demo" / "overview"))
AUDIO = WORK / "audio"
FINAL = WORK / "final"
TIMELINE = WORK / "timeline.json"

W, H, FPS = 1920, 1080, 30
VOICE, ENGINE = "Matthew", "generative"
NAVY, NAVY2, CREAM, AMBER = (20, 33, 61), (36, 55, 96), (245, 239, 227), (200, 129, 26)

# (scene name, planned seconds, narration)
SCENES = [
    ("problem", 9.0, "Every Sunday, a lot of pieces have to come together. The music, the timing, the instruments, the people."),
    ("heart", 12.0, "At the center is the Server. It keeps your hymns, chants, and services, and plays them at the right moment, to your sound system."),
    ("prepare", 12.0, "To prepare, there are two free apps. Templates holds the shape of a service. Services fills it in for Sunday: the date, the hymns, the timing."),
    ("run", 11.0, "On Sunday, Runner is the one you press Play on, on a computer or on a phone. Each item shows what is waiting, what is next, and what is playing."),
    ("instrument", 12.0, "If your organ is across the room, the MIDI Player sits beside it. The Server sends it the music over your church network, and it plays the instrument."),
    ("control", 10.0, "To keep it yours, Administrator decides which devices may connect. Security does the same from a phone, for lost or new devices."),
    ("whole", 9.0, "Seven apps, one picture, all running on your own network. No internet, no account. Just the pieces you need."),
    ("which", 7.0, "Every app has a built-in demo, so you can look around first. Find it all at kng-consulting.com."),
]
NARRATION_DELAY = 0.5      # seconds into a scene before its narration starts
SCENE_TAIL = 0.9           # minimum quiet time after narration ends
# snap moments: piece -> (scene index, seconds into scene)
SNAPS = {
    "templates": (2, 2.2), "services": (2, 6.0), "runner": (3, 2.2),
    "midi": (4, 5.0), "admin": (5, 2.0), "security": (5, 4.0),
}
SERVER_SETTLE = (1, 0.2)   # the Server finishes turning amber
FINAL_SWELL = (6, 4.0)


def load_timeline():
    return json.loads(TIMELINE.read_text())


def scene_start(tl, i):
    return tl["scenes"][i]["start"]


def abs_time(tl, scene, offset):
    return tl["scenes"][scene]["start"] + offset
