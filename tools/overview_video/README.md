# Overview video: "Every Piece in Place"

Code-rendered animated explainer (jigsaw pieces for the apps). Words and design: `Prompts/OverviewVideoStoryboard.md` (private repo). Not linked from the website.

Work area and outputs: `~/Videos/vcm-demo/overview/` (override with `OVERVIEW_WORK`).

    python3 audio.py       # Polly (Matthew) narration, timeline.json, music bed + clicks, audio/mix.wav
    python3 render.py stills 12 40 70   # 2x stills at those seconds, for a quick look
    python3 render.py all  # every frame (about 5 minutes, 8 cores)
    python3 assemble.py    # final/every-piece-in-place.mp4, .webm, .vtt, -transcript.txt, -poster.jpg

Needs Pillow, numpy, ffmpeg, and the `claude-kng` AWS profile (`aws login`) for Polly. If the narration wording changes, edit `SCENES` in `common.py` and the storyboard together, then re-run all three steps in order.
