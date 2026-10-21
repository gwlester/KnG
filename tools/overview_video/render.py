#!/usr/bin/env python3
"""Render the overview video's frames with Pillow (flat vector look, 2x supersampled).

  python3 render.py preview            -> frames/prev/*.png every 2 s (1x, for a quick look)
  python3 render.py stills T [T...]    -> frames/still_T.png at the given seconds
  python3 render.py all                -> frames/f%05d.png for the whole video (parallel)

Everything is drawn from code, so the labels and piece shapes are exact and a re-render is cheap.
"""
import math
import sys
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import common as C

S = 270                       # puzzle cell size in world units
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANSB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
OFF = (232, 224, 206)

CELLS = {"server": (1, 1), "runner": (1, 0), "templates": (0, 1), "services": (0, 0),
         "midi": (2, 1), "admin": (1, 2), "security": (0, 2)}
LABEL = {"server": ("VCM", "Server"), "runner": ("VCM", "Runner"), "templates": ("VCM", "Templates"),
         "services": ("VCM", "Services"), "midi": ("VCM", "MIDI Player"), "admin": ("VCM", "Administrator"),
         "security": ("VCM", "Security")}
PAID = {"server", "midi"}
SEAM_ORDER = ["server", "runner", "templates", "midi", "admin", "services", "security"]
# pile positions (world) and angles for scene 1
PILE = {"server": (330, 380, -14), "runner": (610, 250, 22), "templates": (150, 270, 35), "services": (120, 560, -28),
        "midi": (560, 560, 17), "admin": (380, 640, -40), "security": (690, 430, 51)}
FAR = {"server": (405, 405), "runner": (405, -1500), "templates": (-1500, 405), "services": (-1500, -700),
       "midi": (1900, 405), "admin": (405, 1800), "security": (-1500, 1500)}


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, t0, t1):
    return clamp((t - t0) / (t1 - t0)) if t1 > t0 else (1.0 if t >= t1 else 0.0)


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def lerp(a, b, x):
    return a + (b - a) * x


def mix(c1, c2, x):
    return tuple(int(lerp(a, b, x)) for a, b in zip(c1, c2))


def fade(t, t_in, t_out=None, dur=0.5):
    a = smooth((t - t_in) / dur)
    if t_out is not None:
        a = min(a, 1 - smooth((t - t_out) / dur))
    return clamp(a)


# ---------------------------------------------------------------- piece geometry

def _knob(sign):
    """Profile of a tab along one edge in unit coords: list of (u along edge 0..1, v offset), v in edge units."""
    pts = [(0.0, 0.0), (0.36, 0.0)]
    for i in range(1, 7):                 # quadratic from the flat into the neck
        x = i / 6
        px = (1 - x) ** 2 * 0.36 + 2 * (1 - x) * x * 0.45 + x * x * 0.44
        py = x * x * 0.075
        pts.append((px, py))
    cx, cy, r = 0.5, 0.12, 0.075
    a0 = math.atan2(0.075 - cy, 0.44 - cx)
    a1 = math.atan2(0.075 - cy, 0.56 - cx)
    a0 = a0 + 2 * math.pi if a0 < 0 else a0       # 233 deg
    a1 = a1 if a1 > -math.pi / 2 else a1
    steps = 24
    for i in range(1, steps):
        a = a0 + (a1 - a0) * i / steps
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append((0.56, 0.075))
    pts += [(1 - u, v) for (u, v) in pts[2:9]][::-1]
    pts.append((1.0, 0.0))
    return [(u, v * sign) for (u, v) in pts]


def _edge_sign(a, b):
    return 1 if (a[0] * 3 + a[1] * 5 + b[0] * 7 + b[1] * 11) % 2 == 0 else -1


def piece_polygon(name):
    """Polygon relative to the cell centre, in world units at zoom 1."""
    cx, cy = CELLS[name]
    cells = set(CELLS.values())
    half = S / 2
    corners = [(-half, -half), (half, -half), (half, half), (-half, half)]
    nbrs = [(cx, cy - 1), (cx + 1, cy), (cx, cy + 1), (cx - 1, cy)]
    poly = []
    for k in range(4):
        p0, p1 = corners[k], corners[(k + 1) % 4]
        nb = nbrs[k]
        if nb not in cells:
            poly.append(p0)
            continue
        horizontal = k in (0, 2)
        a, b = sorted([(cx, cy), nb])        # canonical order: lower cell index first
        sign = _edge_sign(a, b)
        prof = _knob(sign)
        # canonical direction: horizontal edges left->right, vertical edges top->bottom
        if horizontal:
            q0 = (-half, p0[1]); q1 = (half, p0[1]); n = (0, 1)
        else:
            q0 = (p0[0], -half); q1 = (p0[0], half); n = (-1, 0)
        pts = [(q0[0] + (q1[0] - q0[0]) * u + n[0] * v * S, q0[1] + (q1[1] - q0[1]) * u + n[1] * v * S) for u, v in prof]
        # traverse in this piece's direction
        forward = (p0[0] <= p1[0] and p0[1] <= p1[1])
        if not forward:
            pts = pts[::-1]
        poly += pts[:-1]
    return poly


POLY = {n: piece_polygon(n) for n in CELLS}


# ---------------------------------------------------------------- canvas

class Canvas:
    def __init__(self, k, cam):
        self.k = k
        self.cx, self.cy, self.z = cam
        self.im = Image.new("RGB", (C.W * k, C.H * k), C.NAVY)
        self.d = ImageDraw.Draw(self.im, "RGBA")
        self._f = {}

    def P(self, x, y):
        return ((x - self.cx) * self.z + C.W / 2) * self.k, ((y - self.cy) * self.z + C.H / 2) * self.k

    def L(self, n):
        return n * self.z * self.k

    def sL(self, n):
        return n * self.k

    def font(self, path, size):
        key = (path, int(size))
        if key not in self._f:
            self._f[key] = ImageFont.truetype(path, max(6, int(size)))
        return self._f[key]

    def text(self, x, y, s, size, fill=C.CREAM, path=SANS, screen=False, anchor="mm", alpha=1.0):
        if alpha <= 0:
            return
        if screen:
            px, py = x * self.k, y * self.k
            f = self.font(path, size * self.k)
        else:
            px, py = self.P(x, y)
            f = self.font(path, size * self.z * self.k)
        self.d.text((px, py), s, font=f, fill=fill + (int(255 * alpha),), anchor=anchor)

    def poly(self, pts, fill=None, outline=None, width=2, alpha=1.0, world=True):
        pp = [self.P(*p) if world else (p[0] * self.k, p[1] * self.k) for p in pts]
        a = int(255 * alpha)
        if fill:
            self.d.polygon(pp, fill=fill + (a,))
        if outline:
            self.d.line(pp + [pp[0]], fill=outline + (a,), width=max(1, int((self.L(width) if world else self.sL(width)))), joint="curve")

    def line(self, pts, fill=C.CREAM, width=3, alpha=1.0, world=True):
        pp = [self.P(*p) if world else (p[0] * self.k, p[1] * self.k) for p in pts]
        w = self.L(width) if world else self.sL(width)
        self.d.line(pp, fill=fill + (int(255 * alpha),), width=max(1, int(w)), joint="curve")

    def rrect(self, x0, y0, x1, y1, r=12, fill=None, outline=None, width=3, alpha=1.0, world=True):
        a, b = (self.P(x0, y0), self.P(x1, y1)) if world else ((x0 * self.k, y0 * self.k), (x1 * self.k, y1 * self.k))
        rr = (self.L(r) if world else self.sL(r))
        self.d.rounded_rectangle([a, b], radius=rr, fill=(fill + (int(255 * alpha),)) if fill else None,
                                 outline=(outline + (int(255 * alpha),)) if outline else None,
                                 width=max(1, int(self.L(width) if world else self.sL(width))))

    def circle(self, x, y, r, fill=None, outline=None, width=3, alpha=1.0):
        cx, cy = self.P(x, y)
        rr = self.L(r)
        self.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(fill + (int(255 * alpha),)) if fill else None,
                       outline=(outline + (int(255 * alpha),)) if outline else None, width=max(1, int(self.L(width))))

    def pill(self, x, y, s, size=26, fill=C.NAVY2, tcolor=C.CREAM, alpha=1.0, screen=False, border=None):
        if alpha <= 0:
            return
        f = self.font(SANSB, size * (self.k if screen else self.z * self.k))
        tw = self.d.textlength(s, font=f)
        pad = size * 0.55 * (self.k if screen else self.z * self.k)
        cx, cy = ((x * self.k, y * self.k) if screen else self.P(x, y))
        h = size * (self.k if screen else self.z * self.k) * 0.95
        self.d.rounded_rectangle([cx - tw / 2 - pad, cy - h / 2 - pad * .35, cx + tw / 2 + pad, cy + h / 2 + pad * .35],
                                 radius=h, fill=fill + (int(235 * alpha),),
                                 outline=(border + (int(255 * alpha),)) if border else None, width=max(1, self.k * 2))
        self.d.text((cx, cy), s, font=f, fill=tcolor + (int(255 * alpha),), anchor="mm")

    def dashed_ellipse(self, cx, cy, rx, ry, fill=C.AMBER, width=4, alpha=1.0, dash=0.07, gap=0.05, phase=0.0, upto=1.0):
        total = 2 * math.pi
        a = phase
        end = phase + total * upto
        while a < end:
            b = min(a + dash * total, end)
            pts = [(cx + rx * math.cos(x), cy + ry * math.sin(x)) for x in [a + (b - a) * i / 6 for i in range(7)]]
            self.line(pts, fill=fill, width=width, alpha=alpha)
            a = b + gap * total


# ---------------------------------------------------------------- icons (local coords, ~ +-60 box, y down)

def icon(cv, name, x, y, s, alpha):
    c = C.CREAM
    w = 3.2

    def P(px, py):
        return (x + px * s, y + py * s)

    def box(a, b, c2, d2, r=6, **kw):
        cv.rrect(*P(a, b), *P(c2, d2), r=r * s, outline=c, width=w * s, alpha=alpha, **kw)

    if name == "server":
        for i, yy in enumerate((-48, -20, 8)):
            box(-46, yy, 46, yy + 22, r=8)
            cv.circle(*P(30, yy + 11), 3 * s, fill=c, alpha=alpha)
        cv.poly([P(-12, 36), P(-12, 62), P(14, 49)], fill=c, alpha=alpha)
    elif name == "templates":
        box(-34, -52, 34, 52)
        cv.line([P(-22, -34), P(22, -34)], fill=c, width=w * s, alpha=alpha)
        for yy in (-8, 20):
            for xx in range(-22, 22, 14):
                cv.line([P(xx, yy), P(xx + 8, yy)], fill=c, width=w * s, alpha=alpha)
    elif name == "services":
        box(-44, -40, 44, 50)
        cv.line([P(-44, -16), P(44, -16)], fill=c, width=w * s, alpha=alpha)
        for yy in (6, 28):
            for xx in (-26, 0, 26):
                cv.circle(*P(xx, yy), 3.5 * s, fill=c, alpha=alpha)
        cv.line([P(-24, -46), P(-24, -32)], fill=c, width=w * s, alpha=alpha)
        cv.line([P(24, -46), P(24, -32)], fill=c, width=w * s, alpha=alpha)
    elif name == "runner":
        box(-56, -36, 18, 26)
        cv.line([P(-40, 38), P(2, 38)], fill=c, width=w * s, alpha=alpha)
        box(26, -14, 56, 46, r=7)
        cv.poly([P(-30, -22), P(-30, 12), P(-4, -5)], fill=c, alpha=alpha)
    elif name == "midi":
        cv.circle(*P(0, 0), 40 * s, outline=c, width=w * s, alpha=alpha)
        for ang in (180, 135, 90, 45, 0):
            a = math.radians(ang + 180)
            cv.circle(*P(24 * math.cos(a), 24 * math.sin(a)), 4.5 * s, fill=c, alpha=alpha)
        cv.line([P(-9, 42), P(-9, 54), P(9, 54), P(9, 42)], fill=c, width=w * s, alpha=alpha)
    elif name in ("admin", "security"):
        sh = [P(0, -50), P(40, -34), P(40, 6), P(0, 50), P(-40, 6), P(-40, -34)]
        cv.poly(sh, outline=c, width=w * s, alpha=alpha)
        if name == "admin":
            cv.line([P(-18, 0), P(-4, 16), P(20, -16)], fill=c, width=(w + 1.5) * s, alpha=alpha)
        else:
            box(-12, -22, 12, 22, r=4)
            cv.circle(*P(0, 14), 2.5 * s, fill=c, alpha=alpha)


# ---------------------------------------------------------------- piece state

def snap_time(tl, name):
    sc, off = C.SNAPS[name]
    return C.abs_time(tl, sc, off)


def piece_state(tl, name, t):
    """Returns dict: pos (x,y), ang (deg), scale, fill, outline, icon_alpha, label_alpha, visible, flash."""
    cx, cy = CELLS[name]
    home = ((cx + .5) * S, (cy + .5) * S)
    s1 = tl["scenes"][0]
    pile = PILE[name]
    far = FAR[name]
    if name == "server":
        t_move0, t_move1 = s1["start"] + 6.4, s1["start"] + 9.3
        x = ease_out(prog(t, t_move0, t_move1))
        px = lerp(pile[0], home[0], x)
        py = lerp(pile[1], home[1], x)
        ang = lerp(pile[2], 0, smooth(prog(t, t_move0, t_move1)))
        a_t0 = C.abs_time(tl, 1, 0.1)
        amber = smooth(prog(t, a_t0, a_t0 + 0.9))
        # gentle hover in the pile before it moves
        hov = 0 if t > t_move0 else math.sin(t * 1.3) * 3
        st = dict(pos=(px, py + hov), ang=ang, scale=lerp(1.0, 1.0, x), fill=mix(OFF, C.AMBER, amber), outline=mix(C.NAVY, C.CREAM, amber),
                  icon_alpha=smooth(prog(t, a_t0 + 0.6, a_t0 + 1.4)), label_alpha=smooth(prog(t, a_t0 + 0.6, a_t0 + 1.4)),
                  visible=True, flash=0.0, flightx=0.0)
        st["flash"] = clamp(1 - (t - a_t0 - 0.9) / 0.6) if t > a_t0 + 0.9 else 0.0
        return st
    ts = snap_time(tl, name)
    fly0, fly1 = ts - 2.1, ts
    exit0, exit1 = s1["start"] + 5.3, s1["start"] + 8.8
    # hidden (off-screen) between exit and entry; placement
    paid = name in PAID
    if t < exit0:
        pos = (pile[0] + math.sin(t * .9 + pile[2]) * 4, pile[1] + math.cos(t * 1.1 + pile[2]) * 4)
        ang = pile[2] + math.sin(t * .7 + pile[2]) * 1.2
        # one piece lifts a few pixels as if the viewer is choosing (scene 1)
        return dict(pos=pos, ang=ang, scale=1.0, fill=OFF, outline=C.NAVY, icon_alpha=0, label_alpha=0, visible=True, flash=0.0)
    if t < fly0:
        x = ease_out(prog(t, exit0, exit1))
        pos = (lerp(pile[0], far[0], x), lerp(pile[1], far[1], x))
        ang = lerp(pile[2], pile[2] + 40, x)
        return dict(pos=pos, ang=ang, scale=1.0, fill=OFF, outline=C.NAVY, icon_alpha=0, label_alpha=0, visible=x < 1.0, flash=0.0)
    x = prog(t, fly0, fly1)
    e = ease_out(x)
    # arc: the approach is bowed sideways
    dx, dy = home[0] - far[0], home[1] - far[1]
    nrm = math.hypot(dx, dy) or 1
    bow = math.sin(math.pi * e) * 160
    pos = (lerp(far[0], home[0], e) - dy / nrm * bow, lerp(far[1], home[1], e) + dx / nrm * bow)
    ang = lerp(pile[2] + 40, 0, e)
    pulse = 1.0 + 0.035 * math.sin(math.pi * clamp((t - ts) / 0.35)) if t >= ts else 1.0
    target = C.AMBER if paid else C.NAVY2
    fill = mix(OFF, target, smooth(prog(t, fly0 + 0.8, fly1)))
    outline = mix(C.NAVY, C.CREAM, smooth(prog(t, fly0 + 0.8, fly1)))
    la = smooth(prog(t, ts, ts + 0.4))
    flash = clamp(1 - (t - ts) / 0.6) if t >= ts else 0.0
    return dict(pos=pos, ang=ang, scale=pulse, fill=fill, outline=outline, icon_alpha=la, label_alpha=la, visible=True, flash=flash)


def draw_piece(cv, name, st, shadow_layer=None):
    if not st["visible"]:
        return
    ca, sa = math.cos(math.radians(st["ang"])), math.sin(math.radians(st["ang"]))
    pts = [(st["pos"][0] + (x * ca - y * sa) * st["scale"], st["pos"][1] + (x * sa + y * ca) * st["scale"]) for x, y in POLY[name]]
    if shadow_layer is not None:
        shadow_layer.polygon([cv.P(x + 8, y + 12) for x, y in pts] if False else [(cv.P(x + 8, y + 12)[0] / cv.k, cv.P(x + 8, y + 12)[1] / cv.k) for x, y in pts], fill=(0, 0, 0, 120))
    cv.poly(pts, fill=st["fill"], outline=st["outline"], width=3)
    if st["flash"] > 0:
        cv.poly(pts, outline=C.AMBER if name not in PAID else (255, 220, 140), width=7, alpha=st["flash"] * 0.9)
    if st["icon_alpha"] > 0:
        px, py = st["pos"]
        icon(cv, name, px, py - 30, 0.78 if name == "server" else 0.72, st["icon_alpha"])
    if st["label_alpha"] > 0:
        px, py = st["pos"]
        cv.text(px, py + 36, LABEL[name][0], 16, C.CREAM, SANS, alpha=st["label_alpha"] * 0.85)
        cv.text(px, py + 58, LABEL[name][1], 24, C.CREAM, SANSB, alpha=st["label_alpha"])


# ---------------------------------------------------------------- camera

def camera(tl, t):
    sc = tl["scenes"]
    st = [s["start"] for s in sc]
    kfs = [  # (time, cx, cy, zoom)
        (st[0], 405, 405, 0.95), (st[1], 405, 405, 1.0), (st[2] - 0.01, 405, 405, 1.12),
        (st[2] + 1.5, 150, 405, 1.0), (st[3] - 0.5, 150, 405, 1.0),
        (st[3] + 1.2, 405, 110, 0.95), (st[4] - 0.5, 405, 110, 0.95),
        (st[4] + 1.2, 640, 380, 0.95), (st[5] - 0.5, 640, 380, 0.95),
        (st[5] + 1.2, 560, 480, 1.0), (st[6] - 0.5, 560, 480, 1.0),
        (st[6] + 6.5, 600, 400, 0.84), (st[7] - 0.2, 600, 400, 0.84),
        (st[7] + 1.2, 1000, 405, 0.78), (st[7] + sc[7]["dur"], 1000, 405, 0.78),
    ]
    if t <= kfs[0][0]:
        return kfs[0][1:]
    for a, b in zip(kfs, kfs[1:]):
        if a[0] <= t <= b[0]:
            x = smooth(prog(t, a[0], b[0]))
            return tuple(lerp(a[i], b[i], x) for i in (1, 2, 3))
    return kfs[-1][1:]


# ---------------------------------------------------------------- props and overlays

def draw_speaker(cv, x, y, alpha, glow=0.0):
    c = C.CREAM
    cv.poly([(x - 36, y - 16), (x - 16, y - 16), (x + 6, y - 38), (x + 6, y + 38), (x - 16, y + 16), (x - 36, y + 16)],
            outline=c, width=3, alpha=alpha)
    for r in (22, 40, 58):
        a = alpha * (0.45 + 0.55 * glow) * (1 - r / 90)
        pts = [(x + 14 + r * math.cos(math.radians(g)), y + r * math.sin(math.radians(g))) for g in range(-40, 41, 8)]
        cv.line(pts, fill=c, width=3, alpha=a)


def draw_wave(cv, x0, y0, x1, y1, upto, alpha):
    pts = []
    n = 60
    for i in range(int(n * upto) + 1):
        u = i / n
        amp = 14 * math.sin(math.pi * u)
        pts.append((lerp(x0, x1, u), lerp(y0, y1, u) + amp * math.sin(u * 28)))
    if len(pts) > 1:
        cv.line(pts, fill=C.AMBER, width=4, alpha=alpha)


def draw_organ(cv, x, y, alpha, glow):
    c = C.CREAM
    heights = [150, 190, 230, 270, 230, 190, 150]
    for i, h in enumerate(heights):
        px = x + i * 42
        cv.rrect(px, y + 280 - h, px + 28, y + 280, r=14, outline=c, width=3, alpha=alpha)
        cv.circle(px + 14, y + 280 - h + 40, 6, outline=c, width=2, alpha=alpha * 0.8)
    cv.rrect(x - 20, y + 280, x + 320, y + 420, r=10, outline=c, width=3, alpha=alpha)
    for i in range(14):
        kx = x - 6 + i * 23
        cv.rrect(kx, y + 340, kx + 20, y + 410, r=3, fill=mix(C.NAVY, C.AMBER, glow * (0.5 + 0.5 * math.sin(i))) if glow else None,
                 outline=c, width=2, alpha=alpha)


def draw_bars(cv, x, y, w, states, alpha):
    """states: 3 bars; 0 waiting (dim), 1 up next (outlined), 2 playing (amber)."""
    for i, s in enumerate(states):
        yy = y + i * 34
        if s == 2:
            cv.rrect(x, yy, x + w, yy + 24, r=8, fill=C.AMBER, alpha=alpha)
        elif s == 1:
            cv.rrect(x, yy, x + w, yy + 24, r=8, outline=C.CREAM, width=3, alpha=alpha)
        else:
            cv.rrect(x, yy, x + w, yy + 24, r=8, fill=(90, 105, 140), alpha=alpha * 0.7)


def draw_cloud(cv, x, y, alpha):
    c = C.CREAM
    for dx, dy, r in ((-34, 6, 26), (0, -8, 36), (36, 6, 26)):
        cv.circle(x + dx, y + dy, r, outline=c, width=3, alpha=alpha)
    cv.rrect(x - 62, y + 6, x + 62, y + 34, r=14, fill=C.NAVY, alpha=alpha)
    cv.line([(x - 60, y + 32), (x + 60, y + 32)], fill=c, width=3, alpha=alpha)
    cv.line([(x - 60, y + 50), (x + 60, y - 50)], fill=C.AMBER, width=6, alpha=alpha)


def draw_ring(cv, tl, t):
    """The 'Your church network' ring: around the Server-to-organ link in scene 5, around everything in scene 7."""
    st = [s["start"] for s in tl["scenes"]]
    a = fade(t, st[6] + 0.2, st[7], 0.9)
    if a <= 0:
        return
    g = smooth(prog(t, st[6], st[6] + 5.0))
    kx, ky = lerp(675, 600, g), lerp(405, 400, g)
    rx, ry = lerp(330, 880, g), lerp(190, 540, g)
    cv.dashed_ellipse(kx, ky, rx, ry, alpha=a, phase=t * 0.15, width=4)
    cv.pill(kx + rx * 0.5, ky + ry * 0.866, "Your church network", 24, fill=C.NAVY, border=C.AMBER, alpha=a)


def overlays(cv, tl, t, states):
    sc = tl["scenes"]
    st = [s["start"] for s in sc]
    u = lambda i: t - st[i]
    home = lambda n: ((CELLS[n][0] + .5) * S, (CELLS[n][1] + .5) * S)

    # ---- scene 1 title
    ta = fade(t, st[0] + 5.2, st[0] + 8.0, 0.8)
    if ta > 0:
        cv.text(C.W / 2, 930, "Virtual Church Musician", 56, C.CREAM, SERIF, screen=True, alpha=ta)

    # ---- scene 2: chips + speaker + waveform
    if t >= st[1]:
        for i, (lab, t0) in enumerate((("Hymns", 3.0), ("Chants", 4.4), ("Services", 5.8))):
            a = fade(t, st[1] + t0, st[1] + t0 + 2.2, 0.4)
            if a > 0:
                m = ease_out(prog(t, st[1] + t0, st[1] + t0 + 1.0))
                hx, hy = home("server")
                xs = (-1, 0, 1)[i]
                cv.pill(hx + xs * 200, hy - 215 + (1 - m) * 30, lab, 26, alpha=a * m)
        la = fade(t, st[1] + 1.4)
        if la > 0 and t < st[2] + 0.5:
            cv.pill(home("server")[0], home("server")[1] + 205, "Stores and plays", 22, fill=C.AMBER, tcolor=C.NAVY, alpha=la * (1 - fade(t, st[2] - 0.4, None, 0.4)))
        sp = fade(t, st[1] + 6.4)
        if sp > 0:
            draw_speaker(cv, 700, 110, sp, glow=(1.0 if t > st[1] + 8 else 0.0))
            wave = prog(t, st[1] + 7.4, st[1] + 9.4)
            draw_wave(cv, 520, 300, 640, 125, wave, sp * (1.0 if t < st[2] else 0.35))

    # ---- scene 3: page with slots
    if st[2] + 1.0 < t < st[3]:
        a = fade(t, st[2] + 2.6, st[3] - 0.8, 0.5)
        if a > 0:
            px, py = -520, 60
            cv.rrect(px, py, px + 360, py + 440, r=18, fill=C.NAVY2, outline=C.CREAM, width=3, alpha=a)
            cv.line([(px + 30, py + 40), (px + 330, py + 40)], fill=C.CREAM, width=5, alpha=a)
            fill = smooth(prog(t, st[2] + 6.6, st[2] + 8.4))
            for i in range(2):
                y0 = py + 90 + i * 100
                if fill > 0 and (i == 0 or fill > 0.5):
                    cv.rrect(px + 30, y0, px + 330, y0 + 70, r=12, fill=C.AMBER, alpha=a)
                    cv.text(px + 180, y0 + 35, ("Opening hymn", "Closing hymn")[i], 24, C.NAVY, SANSB, alpha=a)
                else:
                    cv.rrect(px + 30, y0, px + 330, y0 + 70, r=12, outline=C.CREAM, width=3, alpha=a * 0.9)
            for i in range(3):
                cv.line([(px + 30, py + 300 + i * 38), (px + 30 + (300 if i < 2 else 200), py + 300 + i * 38)], fill=(140, 155, 190), width=5, alpha=a)
            if fill > 0.6:
                cv.pill(px + 180, py + 480, "Sunday", 24, fill=C.AMBER, tcolor=C.NAVY, alpha=a)
            ca = fade(t, st[2] + 3.6, st[2] + 6.6, 0.4)
            cv.pill(px + 180, py - 40, "You choose each week", 24, alpha=ca)
        for nm, t0 in (("templates", 0), ("services", 0)):
            ts = snap_time(tl, nm)
            tag = fade(t, ts + 0.5, st[3], 0.4)
            if tag > 0:
                x, y = home(nm)
                cv.pill(x - 200, y, "Free", 22, fill=C.NAVY, border=C.CREAM, alpha=tag)

    # ---- scene 4: laptop and phone silhouettes
    if st[3] + 2.0 < t < st[4] + 0.5:
        a = fade(t, st[3] + 3.4, st[4] - 0.2, 0.6)
        slide = ease_out(prog(t, st[3] + 3.4, st[3] + 5.0))
        if a > 0:
            lx, ly = lerp(420, 70, slide), -330
            cv.rrect(lx, ly, lx + 380, ly + 240, r=14, fill=C.NAVY2, outline=C.CREAM, width=3, alpha=a)
            cv.rrect(lx - 30, ly + 240, lx + 410, ly + 262, r=8, outline=C.CREAM, width=3, alpha=a)
            adv = prog(t, st[3] + 7.4, st[3] + 8.2)
            states = (2, 1, 0) if adv < 0.5 else (0, 2, 1)
            draw_bars(cv, lx + 30, ly + 60, 320, states, a)
            px = lerp(420, 640, slide)
            cv.rrect(px, ly - 10, px + 190, ly + 270, r=24, fill=C.NAVY2, outline=C.CREAM, width=3, alpha=a)
            draw_bars(cv, px + 22, ly + 60, 146, states, a)
            cv.text(lx + 190, ly + 310, "Computer", 24, C.CREAM, SANSB, alpha=a)
            cv.text(px + 95, ly + 310, "Phone", 24, C.CREAM, SANSB, alpha=a)
            legend = fade(t, st[3] + 5.4, st[4] - 0.2, 0.4)
            cv.pill(405, -400, "Free: on a computer or a phone", 24, alpha=legend)

    # ---- scene 5: organ, MIDI line, ring, notes
    if t >= st[4] + 0.6:
        oa = min(fade(t, st[4] + 1.0), 1 - fade(t, st[7], None, 0.9))
        ox, oy = 1090, 150
        glow = smooth(prog(t, st[4] + 7.0, st[4] + 8.0)) * (0.75 + 0.25 * math.sin(t * 2)) if t > st[4] else 0
        if oa > 0:
            draw_organ(cv, ox, oy, oa, glow)
            ms = snap_time(tl, "midi")
            reach = prog(t, st[4] + 1.5, st[4] + 3.5) * 0.55
            done = prog(t, ms, ms + 0.8)
            frac = 0.55 + 0.45 * done if t >= ms else reach
            x0, x1 = 540, 1070
            cv.line([(x0, 405), (lerp(x0, x1, frac), 405)], fill=C.AMBER, width=5, alpha=oa)
            if t < ms:
                cv.pill(lerp(x0, x1, 0.275), 365, "MIDI", 22, fill=C.AMBER, tcolor=C.NAVY, alpha=oa)
            na2 = fade(t, ms + 0.8, st[5] + 0.4, 0.5)
            if na2 > 0:
                for k in range(4):
                    dxp = lerp(810, 1070, ((t * 0.35 + k / 4) % 1.0))
                    cv.circle(dxp, 405, 7, fill=C.CREAM, alpha=na2 * 0.9)
                cv.pill(940, 352, "Over your church network", 22, fill=C.NAVY, border=C.AMBER, alpha=na2)
            tag = fade(t, ms + 0.6, st[5], 0.4)
            if tag > 0:
                x, y = home("midi")
                cv.pill(x, y + 175, "Paid", 22, fill=C.AMBER, tcolor=C.NAVY, alpha=tag)
            na = fade(t, st[4] + 8.2, st[5] + 1.0, 0.5)
            cv.pill(ox + 150, oy + 480, "Or connect it directly to the Server", 22, alpha=na)

    # ---- scene 6: device approval
    if st[5] + 4.8 < t < st[6] + 1.0:
        a = min(fade(t, st[5] + 5.0), 1 - fade(t, st[6] + 0.2, None, 0.5))
        if a > 0:
            mv = ease_out(prog(t, st[5] + 5.0, st[5] + 7.0))
            dx = lerp(1250, 930, mv)
            ok = smooth(prog(t, st[5] + 8.2, st[5] + 8.8))
            cv.rrect(dx, 600, dx + 90, 740, r=16, fill=(mix(C.NAVY, C.CREAM, ok) if ok else None), outline=C.CREAM, width=3, alpha=a)
            cv.line([(dx, 670), (560, 700)], fill=C.AMBER, width=3, alpha=a * 0.6 * (1 - ok))
            if ok > 0.3:
                cv.line([(dx + 22, 672), (dx + 40, 692), (dx + 70, 650)], fill=C.NAVY, width=7, alpha=a)
            lab = "Approved" if ok > 0.5 else "Waiting for approval"
            cv.pill(dx + 45, 560, lab, 22, fill=C.AMBER if ok > 0.5 else C.NAVY2, tcolor=C.NAVY if ok > 0.5 else C.CREAM, alpha=a * fade(t, st[5] + 6.6))
        for nm in ("admin", "security"):
            tag = fade(t, snap_time(tl, nm) + 0.5, st[6], 0.4)
            if tag > 0:
                x, y = home(nm)
                cv.pill(x - (0 if nm == "admin" else 200), y + (165 if nm == "admin" else 0), "Free", 22, fill=C.NAVY, border=C.CREAM, alpha=tag)

    # ---- scene 7: cloud tag, seam glow
    if t >= st[6] + 4.6:
        a = min(fade(t, st[6] + 4.8), 1 - fade(t, st[7], None, 0.8))
        draw_cloud(cv, 1450, 70, a)
        cv.pill(1450, 160, "No internet needed", 24, alpha=a)
    if st[6] + 3.6 < t < st[7] + 0.6:
        seam = (t - (st[6] + 3.8)) / 2.4
        for i, nm in enumerate(SEAM_ORDER):
            g = clamp(1 - abs(seam * len(SEAM_ORDER) - i) / 1.6) * 0.8
            if g > 0:
                ps = states[nm]
                ca, sa = math.cos(math.radians(ps["ang"])), math.sin(math.radians(ps["ang"]))
                pts = [(ps["pos"][0] + x * ca - y * sa, ps["pos"][1] + x * sa + y * ca) for x, y in POLY[nm]]
                cv.poly(pts, outline=(255, 214, 140), width=6, alpha=g * (1 - fade(t, st[7], None, 0.6)))

    # ---- scene 8: legend and buttons (screen space)
    if t >= st[7] + 1.0:
        a = fade(t, st[7] + 1.2)
        sw = 36
        cv.rrect(960, 330, 960 + sw, 330 + sw, r=8, fill=C.NAVY2, outline=C.CREAM, width=3, alpha=a, world=False)
        cv.text(1020, 348, "Free: download them and try the demo", 34, C.CREAM, SANS, screen=True, anchor="lm", alpha=a)
        cv.rrect(960, 410, 960 + sw, 410 + sw, r=8, fill=C.AMBER, alpha=a, world=False)
        cv.text(1020, 428, "Paid: the Server and the MIDI Player", 34, C.CREAM, SANS, screen=True, anchor="lm", alpha=a)
        b = fade(t, st[7] + 3.2)
        cv.rrect(960, 540, 1250, 620, r=40, fill=C.AMBER, alpha=b, world=False)
        cv.text(1105, 580, "Try the Demo", 32, C.NAVY, SANSB, screen=True, alpha=b)
        cv.rrect(1290, 540, 1560, 620, r=40, outline=C.CREAM, width=3, alpha=b, world=False)
        cv.text(1425, 580, "Download", 32, C.CREAM, SANSB, screen=True, alpha=b)
        cv.text(1260, 720, "kng-consulting.com", 40, C.CREAM, SERIF, screen=True, alpha=fade(t, st[7] + 3.8))
    # fade to navy at the very end
    end = tl["total"]
    if t > end - 1.0:
        cv.d.rectangle([0, 0, cv.im.width, cv.im.height], fill=C.NAVY + (int(255 * smooth((t - (end - 1.0)) / 1.0)),))


# ---------------------------------------------------------------- captions

def captions(tl):
    """List of (start, end, text): one cue per sentence, spread over the narration by character count."""
    cues = []
    for s in tl["scenes"]:
        sentences = [x.strip() for x in s["text"].replace("? ", "?|").replace(". ", ".|").split("|") if x.strip()]
        total = sum(len(x) for x in sentences)
        t0 = s["narr_start"]
        for x in sentences:
            d = s["narr_dur"] * len(x) / total
            cues.append((round(t0, 2), round(t0 + d, 2), x))
            t0 += d
    return cues


def wrap(text, n=62):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + [cur]


def draw_caption(cv, t, cues):
    for a, b, text in cues:
        if a - 0.05 <= t <= b + 0.15:
            lines = wrap(text)
            y = 1010 - (len(lines) - 1) * 24
            for i, ln in enumerate(lines):
                f = cv.font(SANS, 36 * cv.k)
                tw = cv.d.textlength(ln, font=f) / cv.k
                cv.d.rounded_rectangle([(C.W / 2 - tw / 2 - 18) * cv.k, (y + i * 48 - 25) * cv.k, (C.W / 2 + tw / 2 + 18) * cv.k, (y + i * 48 + 25) * cv.k],
                                       radius=10 * cv.k, fill=(10, 16, 34, 200))
                cv.text(C.W / 2, y + i * 48, ln, 36, C.CREAM, SANS, screen=True)
            return


# ---------------------------------------------------------------- frame

_TL = None
_CUES = None


def init():
    global _TL, _CUES
    _TL = C.load_timeline()
    _CUES = captions(_TL)


def frame(args):
    t, k, path, burn = args
    tl = _TL
    cam = camera(tl, t)
    cv = Canvas(k, cam)
    states = {n: piece_state(tl, n, t) for n in CELLS}
    # shadows on a half-resolution layer, blurred
    sh = Image.new("RGBA", (C.W // 2 * 1, C.H // 2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    order = ["server", "templates", "services", "runner", "midi", "admin", "security"]
    for n in order:
        st = states[n]
        if st["visible"]:
            ca, sa = math.cos(math.radians(st["ang"])), math.sin(math.radians(st["ang"]))
            pts = [(st["pos"][0] + (x * ca - y * sa) * st["scale"] + 7, st["pos"][1] + (x * sa + y * ca) * st["scale"] + 12) for x, y in POLY[n]]
            sd.polygon([(cv.P(*p)[0] / k / 2, cv.P(*p)[1] / k / 2) for p in pts], fill=(0, 0, 0, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(6)).resize(cv.im.size, Image.BILINEAR)
    cv.im.paste(Image.new("RGB", cv.im.size, (5, 9, 20)), (0, 0), sh.split()[3])
    cv.d = ImageDraw.Draw(cv.im, "RGBA")
    draw_ring(cv, tl, t)
    for n in order:
        draw_piece(cv, n, states[n])
    overlays(cv, tl, t, states)
    if burn:
        draw_caption(cv, t, _CUES)
    im = cv.im if k == 1 else cv.im.resize((C.W, C.H), Image.LANCZOS)
    im.save(path)
    return path


def main():
    mode = sys.argv[1]
    init()
    fr = C.WORK / "frames"
    fr.mkdir(parents=True, exist_ok=True)
    tl = _TL
    if mode == "stills":
        for s in sys.argv[2:]:
            frame((float(s), 2, fr / f"still_{float(s):06.2f}.png", True))
    elif mode == "preview":
        jobs = [(float(t), 1, fr / "prev" / f"p_{t:05.1f}.png", True) for t in [i * 2.0 for i in range(int(tl["total"] // 2) + 1)]]
        (fr / "prev").mkdir(exist_ok=True)
        with Pool(8, initializer=init) as p:
            list(p.imap_unordered(frame, jobs))
    elif mode == "all":
        n = int(tl["total"] * C.FPS)
        jobs = [(i / C.FPS, 2, fr / f"f{i:05d}.png", True) for i in range(n)]
        with Pool(8, initializer=init) as p:
            for i, _ in enumerate(p.imap_unordered(frame, jobs, chunksize=8)):
                if i % 200 == 0:
                    print(i, "/", n, flush=True)


if __name__ == "__main__":
    main()
