---
platform: MeWe
pairs_with: unit-testing-python-tkinter-desktop-programs.md
---

For the Python folks here: a short writeup on unit testing Tkinter desktop
apps without ever opening a real window in the test suite -- mock every Tk
call, run headless to prove it, keep the actual decisions in plain Python
instead of StringVar/IntVar. Curious how others handle the "few tests that
really do need a live window" problem.

{{post_url}}
