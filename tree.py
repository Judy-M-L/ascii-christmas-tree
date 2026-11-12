#!/usr/bin/env python3
"""ASCII Christmas Tree - a rotating 3D scene rendered as coloured text.
Run: python3 tree.py [--song wish|jingle|silent | --music song.mp3 | --mute]   (Ctrl-C quits). Best in a tall window, 50+ rows.
The scene builds up over ~15 s: needles -> garland -> presents -> ornaments -> lights -> star."""
import math, os, random, shutil, subprocess, sys, tempfile, threading, time, wave
import numpy as np

TAU = math.tau
rng = np.random.default_rng(7)
Y0 = -1.0                         # ground level
YB, YT = Y0 + 0.30, 1.10          # lowest whorl / tip
def radius(h): return 0.80 * (1 - h) ** 0.95

# point store: position, normal (0 = unlit), colour, ambient occlusion, birth time, glyph, kind
NEEDLE, ORNAMENT, PRESENT, STATIC, GROUND = range(5)
P, N, C, AO, BORN, CH, KIND = [], [], [], [], [], [], []
def add(p, n, c, ao, born, ch, kind=STATIC):
    p = np.asarray(p, float); k = len(p)
    P.append(p); N.append(np.broadcast_to(np.asarray(n, float), (k, 3)).copy())
    C.append(np.broadcast_to(np.asarray(c, float), (k, 3)).copy()); AO.append(np.broadcast_to(ao, k).astype(float))
    BORN.append(np.broadcast_to(born, k).astype(float)); CH.append(np.array(list(ch)) if isinstance(ch, str) else np.asarray(ch))
    KIND.append(np.full(k, kind))

# ---------------------------------------------------------------- needles: whorls of branches, tips poking past the cone
tips = []
for y in np.linspace(YB, YT - 0.05, 26):
    h = (y - YB) / (YT - YB); R = radius(h)
    k = max(6, int(R * 44)); a0 = rng.random() * TAU
    for a in np.linspace(0, TAU, k, endpoint=False) + a0:
        L = R * (0.72 + 0.55 * rng.random())                    # uneven lengths -> jagged silhouette
        n = max(8, int(L * 200))
        s = rng.random(n) ** 0.85
        d = np.array([math.cos(a), 0, math.sin(a)]); side = np.array([-d[2], 0, d[0]])
        p = (d * (L * s)[:, None] + np.array([0, y, 0])
             - np.array([0, 1, 0]) * (0.11 * L * s * s)[:, None]           # droop
             + side * rng.normal(0, 0.012, n)[:, None] + rng.normal(0, 0.006, (n, 3)))
        nrm = d * 0.7 + np.array([0, 0.7, 0]) + rng.normal(0, 0.10, (n, 3))
        snow = (s > 0.5) & (rng.random(n) < 0.05 * s)
        add(p[~snow], nrm[~snow], [0, 0, 0], 0.75 + 0.25 * s[~snow], 0, np.full((~snow).sum(), "."), NEEDLE)
        add(p[snow], [0, 1, 0], [0.92, 0.95, 1.0], 1.0, 0, np.full(snow.sum(), "*"))
        tips.append(d * L * 0.95 + np.array([0, y - 0.1 * L, 0]))
tips = np.array(tips); rng.shuffle(tips)

# ---------------------------------------------------------------- trunk
hh, a = np.meshgrid(np.linspace(Y0 - 0.02, YB + 0.15, 40), np.linspace(0, TAU, 40))
hh, a = hh.ravel(), a.ravel()
add(np.stack([0.085 * np.cos(a), hh, 0.085 * np.sin(a)], -1), np.stack([np.cos(a), 0 * a, np.sin(a)], -1),
    np.array([0.42, 0.26, 0.14])[None] * (0.75 + 0.25 * np.sin(hh * 90 + a * 3))[:, None], 1.0, 0, rng.choice(list("|#%"), len(hh)))

# ---------------------------------------------------------------- tinsel garland: drooping gold spiral in swags (glows)
n = 2600; u = np.linspace(0, 1, n); turns = 3.6
hg = 0.03 + 0.90 * u; ag = TAU * turns * u + 0.9
swag = 0.06 * np.abs(np.sin(ag * 2.5)); rg = radius(hg) * 1.03
p = np.stack([rg * np.cos(ag), YB + (YT - YB) * hg - swag, rg * np.sin(ag)], -1) + rng.normal(0, 0.008, (n, 3))
g0 = sum(len(x) for x in P)
add(p, 0, [1.0, 0.80, 0.30], 0.75 + 0.25 * rng.random(n), 3 + 3.5 * u, rng.choice(list("~=-o"), n, p=[.35, .3, .25, .1]))
g1 = sum(len(x) for x in P)

# ---------------------------------------------------------------- ornaments: small shaded balls on branch tips
PALETTE = [[1.0, 0.10, 0.08], [1.0, 0.10, 0.08], [1.0, 0.10, 0.08], [1.0, 0.75, 0.15], [1.0, 0.70, 0.80], [0.90, 0.95, 1.0]]
for i, tp in enumerate(tips[:44]):
    v = rng.normal(size=(14, 3)); v /= np.linalg.norm(v, axis=1, keepdims=True); v[:, 1] *= 0.6
    add(tp * [1.08, 1, 1.08] + [0, -0.045, 0] + v * 0.04, v, PALETTE[i % len(PALETTE)], 1.0, 6 + 0.1 * i, "@" * 14, ORNAMENT)

# ---------------------------------------------------------------- lights: small warm dots that switch on one by one
NL = 170
lt = tips[50:50 + NL] * [1.05, 1, 1.05] + [0, -0.015, 0]
light_phase = rng.random(NL) * TAU
li0 = sum(len(x) for x in P)
add(lt, 0, [1.0, 0.86, 0.38], 1.0, 9 + np.arange(NL) * (4.0 / NL), "o" * NL)
li1 = sum(len(x) for x in P)

# ---------------------------------------------------------------- presents: boxes with a ribbon, faces shaded
def box(cx, cz, w, hh, d, col, ribbon_col, rot, born, y=0.0):
    n = int(7000 * (w * hh + hh * d + w * d) / 0.3)
    p = rng.random((n, 3)) * [w, hh, d] - [w / 2, 0, d / 2]
    ext = np.array([w / 2, hh, d / 2]); face = np.argmax(np.abs(p) / ext, axis=1)
    sgn = np.where(face == 1, 1.0, np.sign(p[np.arange(n), face])); p[np.arange(n), face] = sgn * ext[face]
    nrm = np.zeros((n, 3)); nrm[np.arange(n), face] = sgn
    rib = (np.abs(p[:, 0]) < w * .09) | (np.abs(p[:, 2]) < d * .09)
    cs, sn = math.cos(rot), math.sin(rot)
    rp = np.stack([p[:, 0] * cs - p[:, 2] * sn, p[:, 1], p[:, 0] * sn + p[:, 2] * cs], -1) + [cx, Y0 + y, cz]
    rn = np.stack([nrm[:, 0] * cs - nrm[:, 2] * sn, nrm[:, 1], nrm[:, 0] * sn + nrm[:, 2] * cs], -1)
    add(rp[~rib], rn[~rib], col, 1.0, born, "#" * int((~rib).sum()), PRESENT)
    add(rp[rib], rn[rib], ribbon_col, 1.0, born, "=" * int(rib.sum()))
RED, GOLD, WHITE, PINK, GREEN, BLUE = [1.0, 0.10, 0.08], [1.0, 0.80, 0.22], [0.95, 0.95, 1.0], [1.0, 0.72, 0.82], [0.12, 0.60, 0.25], [0.25, 0.45, 0.95]
box(-1.05, 0.55, .38, .30, .34, RED, GOLD, 0.3, 7.0)
box(1.10, -0.30, .32, .26, .32, PINK, RED, -0.4, 7.4)
box(0.45, 1.10, .34, .24, .34, GOLD, WHITE, 0.8, 7.8)
box(-0.60, -1.10, .24, .36, .24, RED, WHITE, 0.1, 8.2)
box(1.05, 0.85, .28, .20, .28, GREEN, GOLD, 0.5, 8.6)
box(-1.20, -0.40, .40, .28, .36, WHITE, RED, -0.2, 9.0)
box(-1.20, -0.40, .20, .14, .18, RED, GOLD, 0.4, 9.3, y=.28)   # stacked on top
box(0.75, -1.05, .30, .22, .30, BLUE, WHITE, 0.6, 9.6)
box(-0.35, 1.25, .24, .26, .24, GOLD, RED, -0.5, 9.9)
box(1.35, 0.30, .26, .18, .24, RED, WHITE, 0.2, 10.2)
box(-0.10, -1.35, .34, .18, .28, PINK, GOLD, 0.9, 10.5)
box(1.25, 1.20, .22, .24, .22, GREEN, WHITE, -0.3, 10.8)

# ---------------------------------------------------------------- snowy ground: rows of dots, brightest on the far side behind the tree
gx, gz = np.meshgrid(np.arange(-2.8, 2.8, 0.024), np.arange(-2.8, 2.8, 0.085))
gx, gz = gx.ravel(), gz.ravel(); r = np.hypot(gx, gz)
keep = (r > 0.11) & (rng.random(len(gx)) < 0.85); gx, gz, r = gx[keep], gz[keep], r[keep]
add(np.stack([gx, np.full(len(gx), Y0 - 0.02), gz], -1), 0, [0.70, 0.74, 0.82], 0.6 + 0.4 * rng.random(len(gx)), 0,
    rng.choice(list(":.-'"), len(gx), p=[.4, .4, .12, .08]), GROUND)

P = np.concatenate(P); N = np.concatenate(N); C = np.concatenate(C); AO = np.concatenate(AO)
BORN = np.concatenate(BORN); CH = np.concatenate(CH); KIND = np.concatenate(KIND)
LIGHT = np.array([-0.55, 0.45, -0.70]); LIGHT /= np.linalg.norm(LIGHT)
NEEDLE_DARK, NEEDLE_LIGHT = np.array([0.07, 0.34, 0.13]), np.array([0.62, 0.95, 0.62])
RAMP = np.array(list(".:-=%#*"))                 # needle glyph by brightness rank
RAMP_Q = np.array([0.22, 0.48, 0.68, 0.84, 0.94, 0.985])  # share of needles at or below each glyph
JIT = rng.integers(-1, 2, len(P))

def lambert(nx, ny, nz):
    return np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)

# calibrate the glyph ramp once: brightness quantiles of the needles that face the camera
def _calibrate():
    m = KIND == NEEDLE; p = P[m]; n = N[m]
    front = p[:, 2] < 0
    b = (0.35 + 0.95 * lambert(n[:, 0], n[:, 1], n[:, 2]) * 1.0) * AO[m] * np.clip(0.95 - 0.15 * p[:, 2], 0.75, 1.1)
    return np.quantile(b[front], RAMP_Q)
EDGES = _calibrate()

STARS = []
def make_stars(W, H):
    return [(random.randrange(W), random.randrange(int(H * 0.72)), random.random()) for _ in range(W * H // 45)]

# falling snow (screen space): depth b -> near flakes are big, fast and pass in front of the tree
SNOW = {}
def make_snow(W, H):
    k = W * H // 14
    SNOW.update(x=rng.random(k) * W, y=rng.random(k) * H, b=rng.random(k) ** 2, ph=rng.random(k) * TAU)

# ---------------------------------------------------------------- render
def frame(t, ang, W, H):
    c, s = math.cos(ang), math.sin(ang)
    vis = BORN <= t
    p = P[vis]; n = N[vis]; col = C[vis].copy(); ao = AO[vis]; ch = CH[vis].copy(); kind = KIND[vis]
    x = p[:, 0] * c - p[:, 2] * s; z = p[:, 0] * s + p[:, 2] * c; y = p[:, 1]
    nx = n[:, 0] * c - n[:, 2] * s; nz = n[:, 0] * s + n[:, 2] * c
    CAM = 4.2; d = z + CAM; f = H * 0.40 * CAM
    sx = (W / 2 + 2.0 * f * x / d).astype(int)
    sy = (H * 0.50 - f * (y - 0.06) / d).astype(int)
    ndl = lambert(nx, n[:, 1], nz)
    lit = np.any(n != 0, axis=1)
    bright = np.where(lit, 0.35 + 0.95 * ndl, 1.0) * ao * np.clip(0.95 - 0.15 * z, 0.75, 1.1)

    # needles: glyph and colour from brightness rank -> sparse dark base with bright sparkles
    m = kind == NEEDLE
    rank = np.clip(np.searchsorted(EDGES, bright[m]) + JIT[vis][m], 0, len(RAMP) - 1)
    ch[m] = RAMP[rank]
    q = (rank / (len(RAMP) - 1))[:, None] ** 1.4
    col[m] = NEEDLE_DARK + (NEEDLE_LIGHT - NEEDLE_DARK) * q
    # ornaments: bright @ centre, dark % rim
    m = kind == ORNAMENT
    ch[m] = np.where(ndl[m] > 0.45, "@", "%"); col[m] *= (0.35 + 0.8 * ndl[m])[:, None]
    # presents: face shading picks the glyph
    m = kind == PRESENT
    ch[m] = np.where(ndl[m] > 0.55, "#", np.where(ndl[m] > 0.2, "%", ":")); col[m] *= (0.45 + 0.7 * ndl[m])[:, None]
    # everything else lit normally; ground brighter on the far side (behind the tree)
    m = (kind == STATIC) & lit; col[m] *= bright[m][:, None]
    m = kind == GROUND; col[m] *= (ao[m] * (0.35 + 0.65 * np.clip((z[m] + 0.3) / 2.0, 0, 1)))[:, None]
    # lights blink
    vi = np.flatnonzero(vis); lmask = (vi >= li0) & (vi < li1)
    on = np.sin(t * 2.4 + light_phase[:lmask.sum()]) > -0.3
    col[lmask] = np.where(on[:, None], [1.0, 0.88, 0.40], [0.45, 0.33, 0.10])

    ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
    order = np.argsort(-d[ok], kind="stable")
    gx, gy = sx[ok][order], sy[ok][order]
    grid = np.full((H, W), " ", dtype="<U1"); rgb = np.zeros((H, W, 3))
    grid[gy, gx] = ch[ok][order]; rgb[gy, gx] = col[ok][order]
    emis = np.zeros((H, W, 3))                                   # emissive layer for bloom
    lm = lmask[ok][order]; emis[gy[lm], gx[lm]] = [1.0, 0.80, 0.30]
    gm = ((vi >= g0) & (vi < g1))[ok][order]; emis[gy[gm], gx[gm]] += [0.4, 0.3, 0.1]

    # background stars (twinkle), only on empty cells
    for i, (bx, by, b) in enumerate(STARS):
        if bx < W and by < H and grid[by, bx] == " ":
            tw = 0.5 + 0.5 * math.sin(t * (1.5 + b * 2) + i)
            grid[by, bx] = "+" if b > 0.93 and tw > 0.8 else "."
            rgb[by, bx] = 0.35 + 0.65 * b * tw
    # snow, straight down; near flakes faster
    b = SNOW["b"]; fy = ((SNOW["y"] + t * (2.0 + 7.0 * b)) % H).astype(int); fx = SNOW["x"].astype(int)
    near = b > 0.55; far = ~near & (grid[fy, fx] == " ")
    grid[fy[far], fx[far]] = "."; rgb[fy[far], fx[far]] = (0.35 + 0.5 * b[far])[:, None]
    grid[fy[near], fx[near]] = np.where(b[near] > 0.8, "*", "."); rgb[fy[near], fx[near]] = 0.75 + 0.25 * b[near][:, None]
    # the star: a dense gold block with eight thin rays that grow in
    if t >= 13:
        g = min(1.0, (t - 13) / 1.5)
        tx, ty = int(W / 2), int(H * 0.50 - f * (YT + 0.04 - 0.06) / CAM)
        glow = 0.9 + 0.1 * math.sin(t * 5)
        for j, row in enumerate(["##", "######", "######", "##"]):
            for i, chr_ in enumerate(row):
                yy, xx = ty - 1 + j, tx - len(row) // 2 + i
                if 0 <= yy < H and 0 <= xx < W: grid[yy, xx] = chr_; rgb[yy, xx] = [1.0, 0.92, 0.45 * glow]; emis[yy, xx] = [1.0, 0.9, 0.4]
        rays = [(0, -1, "|", 2, 8), (0, 1, "|", 3, 6), (1, -1, "\\", 2, 6), (-1, -1, "/", 2, 6), (1, 1, "/", 3, 4), (-1, 1, "\\", 3, 4),
                (2, 0, "-", 4, 6), (-2, 0, "-", 4, 6)]
        for ddx, ddy, chr_, k0, ln in rays:
            for k in range(k0, k0 + int(ln * g)):
                yy, xx = ty + k * ddy, tx + k * ddx + (ddx > 0) - (ddx < 0 and ddy == 0)
                if 0 <= yy < H and 0 <= xx < W and (grid[yy, xx] == " " or ddx == 0):
                    frac = (k - k0) / ln
                    grid[yy, xx] = chr_; rgb[yy, xx] = np.array([1.0, 0.88, 0.40]) * (1.0 - 0.7 * frac)
    rgb += bloom(emis)
    return grid, np.clip(rgb * 255, 0, 255).astype(int), int(lmask.sum())

def bloom(e):
    """Cheap glow: spread the emissive layer over a 5x3 neighbourhood (cells are ~2x taller than wide)."""
    out = np.zeros_like(e)
    for ddx, ddy, w in ((1, 0, .45), (-1, 0, .45), (2, 0, .22), (-2, 0, .22), (0, 1, .25), (0, -1, .25),
                        (1, 1, .15), (-1, 1, .15), (1, -1, .15), (-1, -1, .15), (3, 0, .08), (-3, 0, .08)):
        out[max(0, ddy):e.shape[0] + min(0, ddy), max(0, ddx):e.shape[1] + min(0, ddx)] += \
            w * e[max(0, -ddy):e.shape[0] + min(0, -ddy), max(0, -ddx):e.shape[1] + min(0, -ddx)]
    return out * 0.6

TRUECOLOR = os.environ.get("TERM_PROGRAM") != "Apple_Terminal" or os.environ.get("COLORTERM") in ("truecolor", "24bit")
def esc(r, g, b):
    if TRUECOLOR: return f"\x1b[38;2;{r};{g};{b}m"
    return f"\x1b[38;5;{16 + 36 * (r * 6 // 256) + 6 * (g * 6 // 256) + b * 6 // 256}m"
def to_text(grid, rgb):
    q = rgb // 24 * 24                               # quantise so colour runs merge
    out = []; last = None
    for row, crow in zip(grid, q):
        line = []
        for chr_, (r, g, b) in zip(row, crow.tolist()):
            if chr_ != " " and (r, g, b) != last:
                line.append(esc(r, g, b)); last = (r, g, b)
            line.append(chr_)
        out.append("".join(line))
    return "\n".join(out) + "\x1b[0m"

# ---------------------------------------------------------------- music (macOS afplay; --song wish|jingle|silent, --music FILE for your own, --mute)
NOTE = {"C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.00, "A4": 440.00, "B4": 493.88,
        "C5": 523.25, "D5": 587.33, "E5": 659.25, "F5": 698.46}
SONGS = {
    "wish": (0.40, [  # We Wish You a Merry Christmas, 3/4, loops on the pickup note
        ("G4", 1), ("C5", 1), ("C5", .5), ("D5", .5), ("C5", .5), ("B4", .5), ("A4", 1), ("A4", 1), ("A4", 1),
        ("D5", 1), ("D5", .5), ("E5", .5), ("D5", .5), ("C5", .5), ("B4", 1), ("G4", 1), ("G4", 1),
        ("E5", 1), ("E5", .5), ("F5", .5), ("E5", .5), ("D5", .5), ("C5", 1), ("A4", 1), ("G4", .5), ("G4", .5),
        ("A4", 1), ("D5", 1), ("B4", 1), ("C5", 2)]),
    "silent": (0.55, [  # Silent Night, 3/4
        ("G4", 1.5), ("A4", .5), ("G4", 1), ("E4", 3), ("G4", 1.5), ("A4", .5), ("G4", 1), ("E4", 3),
        ("D5", 2), ("D5", 1), ("B4", 3), ("C5", 2), ("C5", 1), ("G4", 3),
        ("A4", 2), ("A4", 1), ("C5", 1.5), ("B4", .5), ("A4", 1), ("G4", 1.5), ("A4", .5), ("G4", 1), ("E4", 3),
        ("A4", 2), ("A4", 1), ("C5", 1.5), ("B4", .5), ("A4", 1), ("G4", 1.5), ("A4", .5), ("G4", 1), ("E4", 3),
        ("D5", 2), ("D5", 1), ("F5", 1.5), ("D5", .5), ("B4", 1), ("C5", 3), ("E5", 3),
        ("C5", 1), ("G4", 1), ("E4", 1), ("G4", 1.5), ("F4", .5), ("D4", 1), ("C4", 6)]),
    "jingle": (0.33, [  # Jingle Bells chorus
        ("E4", 1), ("E4", 1), ("E4", 2), ("E4", 1), ("E4", 1), ("E4", 2), ("E4", 1), ("G4", 1), ("C4", 1.5), ("D4", .5), ("E4", 4),
        ("F4", 1), ("F4", 1), ("F4", 1.5), ("F4", .5), ("F4", 1), ("E4", 1), ("E4", 1), ("E4", .5), ("E4", .5),
        ("E4", 1), ("D4", 1), ("D4", 1), ("E4", 1), ("D4", 2), ("G4", 2)]),
}
def song_wav(name):
    """A carol as a soft little synth tune, written to a temp .wav."""
    sr, (beat, tune), out = 22050, SONGS[name], []
    for n, d in tune:
        tt = np.arange(int(sr * beat * d)) / sr
        env = np.minimum(tt * 60, 1) * np.exp(-tt * 2.2) * (tt < beat * d - 0.02)
        f = NOTE[n]
        out.append(env * (0.26 * np.sin(TAU * f * tt) + 0.10 * np.sign(np.sin(TAU * f * tt)) + 0.08 * np.sin(TAU * 2 * f * tt) + 0.08 * np.sin(TAU * f / 2 * tt)))
    out.append(np.zeros(int(sr * (1.5 if name == "silent" else 0.3))))
    a = (np.concatenate(out) * 32767).astype("<i2")
    path = os.path.join(tempfile.gettempdir(), f"tree_{name}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(a.tobytes())
    return path
player = [None]
def start_music(path):
    if not shutil.which("afplay"): return
    def loop():
        while player[0] is not False:
            player[0] = subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if player[0].wait(): break                   # afplay failed -> stop looping
    threading.Thread(target=loop, daemon=True).start()
def stop_music():
    p = player[0]; player[0] = False
    if p: p.terminate()

def main():
    if "--mute" not in sys.argv:
        song = sys.argv[sys.argv.index("--song") + 1] if "--song" in sys.argv else "wish"
        start_music(sys.argv[sys.argv.index("--music") + 1] if "--music" in sys.argv else song_wav(song))
    W, H = shutil.get_terminal_size((100, 50)); H -= 3
    STARS[:] = make_stars(W, H); make_snow(W, H)
    sys.stdout.write("\x1b[?25l\x1b[2J"); t0 = time.time(); fps = 30; k = 0
    try:
        while True:
            t = time.time() - t0; ang = (t * 0.45) % TAU
            grid, rgb, nlit = frame(t, ang, W, H)
            letters = int((grid != " ").sum())
            status = (f"\x1b[38;5;245mrotation {math.degrees(ang):7.2f}°    lights {nlit:3d}    letters {letters:,}"
                      f"\n\x1b[38;5;240mtree.py{' ' * max(1, W - 24)}running · {fps} fps\x1b[0m")
            sys.stdout.write("\x1b[H" + to_text(grid, rgb) + "\n" + status); sys.stdout.flush()
            k += 1; time.sleep(max(0, t0 + k / fps - time.time()))
    except KeyboardInterrupt:
        pass
    finally:
        stop_music(); sys.stdout.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H"); sys.stdout.flush()

if __name__ == "__main__":
    if "--check" in sys.argv:                        # one full-scene frame must contain every part
        STARS[:] = make_stars(100, 50); make_snow(100, 50)
        g, c, nl = frame(20.0, 0.3, 100, 50)
        assert nl == NL and (g != " ").sum() > 2000 and "#" in g and (c[..., 0] > 200).any(), "render broke"
        p = song_wav("wish"); assert os.path.getsize(p) > 100000; song_wav("jingle"); song_wav("silent")
        print("ok", (g != " ").sum(), "wav", p); sys.exit()
    main()
