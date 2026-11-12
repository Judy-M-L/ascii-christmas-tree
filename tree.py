#!/usr/bin/env python3
"""ASCII Christmas Tree - a rotating 3D scene rendered as coloured text.
Run: python3 tree.py [--music song.mp3 | --mute]   (Ctrl-C quits). Best in a tall window, 50+ rows.
The scene builds up over ~15 s: needles -> garland -> presents -> ornaments -> lights -> star."""
import math, os, random, shutil, subprocess, sys, tempfile, threading, time, wave
import numpy as np

TAU = math.tau
rng = np.random.default_rng(7)
Y0 = -1.0                         # ground level
YB, YT = Y0 + 0.30, 1.10          # lowest whorl / tip
def radius(h): return 0.80 * (1 - h) ** 0.95

# point store: position, normal (0 = unlit flat), colour (rgb 0..1), ambient occlusion, birth time, char
P, N, C, AO, BORN, CH = [], [], [], [], [], []
def add(p, n, c, ao, born, ch):
    p = np.asarray(p, float); k = len(p)
    P.append(p); N.append(np.broadcast_to(np.asarray(n, float), (k, 3)).copy())
    C.append(np.broadcast_to(np.asarray(c, float), (k, 3)).copy()); AO.append(np.broadcast_to(ao, k).astype(float))
    BORN.append(np.broadcast_to(born, k).astype(float)); CH.append(np.array(list(ch)) if isinstance(ch, str) else np.asarray(ch))

# ---------------------------------------------------------------- needles: whorls of drooping branches
tips = []
for y in np.linspace(YB, YT - 0.05, 30):
    h = (y - YB) / (YT - YB); R = radius(h)
    k = max(7, int(R * 52)); a0 = rng.random() * TAU
    for a in np.linspace(0, TAU, k, endpoint=False) + a0:
        L = R * (0.85 + 0.3 * rng.random()); n = max(8, int(L * 210))
        s = 1 - rng.random(n) ** 1.6                       # dense at the tip
        d = np.array([math.cos(a), 0, math.sin(a)])
        side = np.array([-d[2], 0, d[0]])
        p = (d * (L * s)[:, None] + np.array([0, y, 0])
             - np.array([0, 1, 0]) * (0.09 * L * s * s)[:, None]        # droop
             + side * rng.normal(0, 0.016, n)[:, None] + rng.normal(0, 0.007, (n, 3)))
        nrm = d * 0.75 + np.array([0, 0.65, 0]) + rng.normal(0, 0.25, (n, 3))
        col = np.array([0.15, 0.55, 0.24]) + np.array([0.10, 0.35, 0.12]) * rng.random(n)[:, None] ** 2
        ch = np.where(s < 0.35, rng.choice(list("=-:"), n), rng.choice(list("*+%#x:"), n, p=[.3, .25, .15, .1, .1, .1]))
        snow = (s > 0.45) & (rng.random(n) < 0.06 * s)
        add(p[~snow], nrm[~snow], col[~snow], 0.58 + 0.42 * s[~snow], 0, ch[~snow])
        add(p[snow], [0, 1, 0], [0.92, 0.95, 1.0], 1.0, 0, np.full(snow.sum(), "*"))
        tips.append(d * L * 0.93 + np.array([0, y - 0.1 * L, 0]))
tips = np.array(tips); rng.shuffle(tips)

# ---------------------------------------------------------------- trunk with bark
hh, a = np.meshgrid(np.linspace(Y0 - 0.02, YB + 0.15, 40), np.linspace(0, TAU, 40))
hh, a = hh.ravel(), a.ravel()
p = np.stack([0.085 * np.cos(a), hh, 0.085 * np.sin(a)], -1)
nn = np.stack([np.cos(a), 0 * a, np.sin(a)], -1)
bark = 0.75 + 0.25 * np.sin(hh * 90 + a * 3)
add(p, nn, np.array([0.42, 0.26, 0.14])[None] * bark[:, None], 1.0, 0, rng.choice(list("|#%"), len(p)))

# ---------------------------------------------------------------- tinsel garland: drooping gold spiral in swags
n = 2600; u = np.linspace(0, 1, n); turns = 3.6
hg = 0.03 + 0.90 * u; ag = TAU * turns * u + 0.9
swag = 0.06 * np.abs(np.sin(ag * 2.5)); rg = radius(hg) * 1.03
p = np.stack([rg * np.cos(ag), YB + (YT - YB) * hg - swag, rg * np.sin(ag)], -1) + rng.normal(0, 0.008, (n, 3))
add(p, 0, [1.0, 0.80, 0.30], 0.75 + 0.25 * rng.random(n), 3 + 3.5 * u, rng.choice(list("~=-o"), n, p=[.35, .3, .25, .1]))

# ---------------------------------------------------------------- ornaments: little shaded spheres hung from branch tips
def sphere(c, r, col, born, chars="@#%O", k=16):
    v = rng.normal(size=(k, 3)); v /= np.linalg.norm(v, axis=1, keepdims=True)
    add(c + v * r, v, col, 1.0, born, rng.choice(list(chars), k))
PALETTE = [[0.90, 0.12, 0.10], [0.90, 0.12, 0.10], [0.95, 0.72, 0.20], [0.96, 0.78, 0.86], [0.85, 0.90, 0.95]]
for i, tp in enumerate(tips[:34]):
    sphere(tp * [1.07, 1, 1.07] + [0, -0.04, 0], 0.05, PALETTE[i % len(PALETTE)], 6 + 0.1 * i, k=26)

# ---------------------------------------------------------------- lights: warm dots on branch tips, counted in as they switch on
NL = 170
lt = tips[40:40 + NL] * [1.05, 1, 1.05] + [0, -0.015, 0]
light_phase = rng.random(NL) * TAU
light_born = 9 + np.arange(NL) * (4.0 / NL)
li0 = sum(len(x) for x in P)
add(lt, 0, [1.0, 0.86, 0.38], 1.0, light_born, rng.choice(list("o@"), NL))
li1 = sum(len(x) for x in P)

# ---------------------------------------------------------------- presents: boxes with a ribbon, surface only
def box(cx, cz, w, hh, d, col, ribbon_col, rot, born, y=0.0):
    n = int(7000 * (w * hh + hh * d + w * d) / 0.3)
    p = rng.random((n, 3)) * [w, hh, d] - [w / 2, 0, d / 2]
    ext = np.array([w / 2, hh, d / 2])
    face = np.argmax(np.abs(p) / ext, axis=1)                                      # snap to nearest face
    sgn = np.where(face == 1, 1.0, np.sign(p[np.arange(n), face]))
    p[np.arange(n), face] = sgn * ext[face]
    nrm = np.zeros((n, 3)); nrm[np.arange(n), face] = sgn
    rib = (np.abs(p[:, 0]) < w * .09) | (np.abs(p[:, 2]) < d * .09)
    cs, sn = math.cos(rot), math.sin(rot)
    rp = np.stack([p[:, 0] * cs - p[:, 2] * sn, p[:, 1], p[:, 0] * sn + p[:, 2] * cs], -1) + [cx, Y0 + y, cz]
    rn = np.stack([nrm[:, 0] * cs - nrm[:, 2] * sn, nrm[:, 1], nrm[:, 0] * sn + nrm[:, 2] * cs], -1)
    add(rp[~rib], rn[~rib], col, 1.0, born, rng.choice(list("#%@"), (~rib).sum()))
    add(rp[rib], rn[rib], ribbon_col, 1.0, born, np.full(rib.sum(), "="))
box(-0.80, 0.40, .26, .20, .24, [0.85, 0.10, 0.10], [0.95, 0.75, 0.25], 0.3, 7.0)
box(0.85, -0.25, .22, .18, .22, [0.92, 0.80, 0.85], [0.85, 0.10, 0.10], -0.4, 7.4)
box(0.30, 0.85, .24, .16, .24, [0.95, 0.72, 0.20], [0.92, 0.92, 0.95], 0.8, 7.8)
box(-0.45, -0.85, .17, .26, .17, [0.85, 0.10, 0.10], [0.92, 0.92, 0.95], 0.1, 8.2)
box(0.80, 0.70, .20, .14, .20, [0.10, 0.45, 0.20], [0.95, 0.75, 0.25], 0.5, 8.6)
box(-0.95, -0.35, .30, .22, .26, [0.92, 0.92, 0.95], [0.85, 0.10, 0.10], -0.2, 9.0)
box(-0.95, -0.35, .16, .12, .14, [0.85, 0.10, 0.10], [0.95, 0.75, 0.25], 0.4, 9.3, y=.22)   # stacked on top
box(0.60, -0.80, .22, .16, .22, [0.20, 0.35, 0.75], [0.92, 0.92, 0.95], 0.6, 9.6)
box(-0.30, 0.95, .18, .20, .18, [0.95, 0.72, 0.20], [0.85, 0.10, 0.10], -0.5, 9.9)
box(1.05, 0.25, .20, .14, .18, [0.85, 0.10, 0.10], [0.92, 0.92, 0.95], 0.2, 10.2)
box(-0.10, -1.05, .26, .14, .22, [0.92, 0.80, 0.85], [0.95, 0.75, 0.25], 0.9, 10.5)
box(0.95, 0.95, .16, .18, .16, [0.10, 0.45, 0.20], [0.92, 0.92, 0.95], -0.3, 10.8)

# ---------------------------------------------------------------- snowy ground: dotted grid, bright near the tree, fading out
gx, gz = np.meshgrid(np.arange(-2.8, 2.8, 0.032), np.arange(-2.8, 2.8, 0.10))
gx, gz = gx.ravel(), gz.ravel(); r = np.hypot(gx, gz)
keep = (r > 0.11) & (rng.random(len(gx)) < 0.8); gx, gz, r = gx[keep], gz[keep], r[keep]
fade = np.clip(1.25 - 0.33 * r, 0.3, 1.0) * (0.75 + 0.25 * rng.random(len(gx)))
add(np.stack([gx, np.full(len(gx), Y0 - 0.02), gz], -1), 0, [0.72, 0.76, 0.84], fade, 0,
    rng.choice(list(".-:'"), len(gx), p=[.6, .25, .08, .07]))

P = np.concatenate(P); N = np.concatenate(N); C = np.concatenate(C); AO = np.concatenate(AO)
BORN = np.concatenate(BORN); CH = np.concatenate(CH)
LIT = np.any(N != 0, axis=1)
LIGHT = np.array([-0.45, 0.55, -0.70]); LIGHT /= np.linalg.norm(LIGHT)

STARS = []
def make_stars(W, H):
    return [(random.randrange(W), random.randrange(int(H * 0.72)), random.random()) for _ in range(W * H // 45)]

# falling snow (screen space): depth b -> near flakes are big, fast and pass in front of the tree
SNOW = {}
def make_snow(W, H):
    k = W * H // 12
    SNOW.update(x=rng.random(k) * W, y=rng.random(k) * H, b=rng.random(k) ** 2, ph=rng.random(k) * TAU)

# ---------------------------------------------------------------- render
def frame(t, ang, W, H):
    c, s = math.cos(ang), math.sin(ang)
    vis = BORN <= t
    p = P[vis]; n = N[vis]; col = C[vis].copy(); ao = AO[vis]; ch = CH[vis]
    x = p[:, 0] * c - p[:, 2] * s; z = p[:, 0] * s + p[:, 2] * c; y = p[:, 1]
    nx = n[:, 0] * c - n[:, 2] * s; nz = n[:, 0] * s + n[:, 2] * c
    CAM = 4.2; d = z + CAM; f = H * 0.40 * CAM
    sx = (W / 2 + 2.0 * f * x / d).astype(int)
    sy = (H * 0.50 - f * (y - 0.06) / d).astype(int)
    # lighting: lambert + ambient occlusion + a little depth fade; unlit points keep their colour
    ndl = np.clip(nx * LIGHT[0] + n[:, 1] * LIGHT[1] + nz * LIGHT[2], 0, 1)
    lit = np.any(n != 0, axis=1)
    bright = np.where(lit, 0.80 + 0.45 * ndl, 1.0) * ao * np.clip(0.95 - 0.15 * z, 0.75, 1.1)
    col *= bright[:, None]
    # lights blink
    vl = vis[li0:li1]; vi = np.flatnonzero(vis)
    lmask = (vi >= li0) & (vi < li1)
    on = np.sin(t * 2.4 + light_phase[:vl.sum()]) > -0.3
    col[lmask] = np.where(on[:, None], [1.0, 0.88, 0.40], [0.40, 0.30, 0.10])
    nlit = int(vl.sum())

    ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
    order = np.argsort(-d[ok], kind="stable")
    gx, gy = sx[ok][order], sy[ok][order]
    grid = np.full((H, W), " ", dtype="<U1"); rgb = np.zeros((H, W, 3))
    grid[gy, gx] = ch[ok][order]; rgb[gy, gx] = col[ok][order]
    # warm glow around lit bulbs
    lm = lmask[ok][order]; lx, ly = gx[lm], gy[lm]
    for ddx, ddy, g in ((1, 0, .5), (-1, 0, .5), (0, 1, .25), (0, -1, .25), (2, 0, .2), (-2, 0, .2)):
        qx, qy = lx + ddx, ly + ddy; m = (qx >= 0) & (qx < W) & (qy >= 0) & (qy < H)
        rgb[qy[m], qx[m]] += np.array([1.0, 0.75, 0.2]) * g

    # background stars (twinkle), only on empty cells
    for i, (bx, by, b) in enumerate(STARS):
        if bx < W and by < H and grid[by, bx] == " ":
            tw = 0.5 + 0.5 * math.sin(t * (1.5 + b * 2) + i)
            grid[by, bx] = "+" if b > 0.93 and tw > 0.8 else "."
            rgb[by, bx] = 0.35 + 0.65 * b * tw
    # snow
    b = SNOW["b"]; ph = SNOW["ph"]
    gust = 4.0 * math.sin(t * 0.35) + 2.0 * math.sin(t * 1.1 + 1)            # shared wind, changes direction
    fy = (SNOW["y"] + t * (2.0 + 7.0 * b) + 1.5 * np.sin(t * 2.0 + ph)) % H  # tumble up and down a little
    fx = (SNOW["x"] + (3 + 4 * b) * np.sin(t * (0.8 + b) + ph) + gust * (0.5 + b) * t * 0.4) % W
    fx, fy = fx.astype(int), fy.astype(int)
    near = b > 0.55
    far = ~near & (grid[fy, fx] == " ")
    grid[fy[far], fx[far]] = "."; rgb[fy[far], fx[far]] = (0.35 + 0.5 * b[far])[:, None]
    grid[fy[near], fx[near]] = np.where(b[near] > 0.85, "*", "+"); rgb[fy[near], fx[near]] = 0.75 + 0.25 * b[near][:, None]
    # the star: a gold block with rays that grow in
    if t >= 13:
        g = min(1.0, (t - 13) / 1.5)
        tx, ty = int(W / 2), int(H * 0.50 - f * (YT + 0.02 - 0.06) / CAM)
        glow = 0.85 + 0.15 * math.sin(t * 5)
        for j, row in enumerate(["####", "######", "####"]):
            for i, chr_ in enumerate(row):
                yy, xx = ty - 1 + j, tx - len(row) // 2 + i
                if 0 <= yy < H and 0 <= xx < W: grid[yy, xx] = chr_; rgb[yy, xx] = [1.0, 0.90, 0.35 * glow]
        rays = [(0, -1, "|", 9), (0, 1, "|", 4), (2, 0, "-", 7), (-2, 0, "-", 7),
                (2, -1, "/", 5), (-2, -1, "\\", 5), (2, 1, "\\", 4), (-2, 1, "/", 4)]
        for ddx, ddy, chr_, ln in rays:
            for k in range(2, 2 + int(ln * g)):
                yy, xx = ty + k * ddy, tx + k * ddx + (1 if ddx > 0 else 0)
                if 0 <= yy < H and 0 <= xx < W and grid[yy, xx] == " ":
                    grid[yy, xx] = chr_; rgb[yy, xx] = np.array([1.0, 0.85, 0.35]) * (1.1 - k / (ln + 2)) * 0.8
    return grid, np.clip(rgb * 255, 0, 255).astype(int), nlit

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

# ---------------------------------------------------------------- music (macOS afplay; --music FILE for your own song, --mute for none)
NOTE = {"C": 261.63, "D": 293.66, "E": 329.63, "F": 349.23, "G": 392.00}
JINGLE = [("E", 1), ("E", 1), ("E", 2), ("E", 1), ("E", 1), ("E", 2), ("E", 1), ("G", 1), ("C", 1.5), ("D", .5), ("E", 4),
          ("F", 1), ("F", 1), ("F", 1.5), ("F", .5), ("F", 1), ("E", 1), ("E", 1), ("E", .5), ("E", .5),
          ("E", 1), ("D", 1), ("D", 1), ("E", 1), ("D", 2), ("G", 2)]
def jingle_wav():
    """Jingle Bells chorus as a little chiptune, written to a temp .wav."""
    sr, beat, out = 22050, 60 / 180, []
    for n, d in JINGLE:
        tt = np.arange(int(sr * beat * d)) / sr
        env = np.exp(-tt * 3) * (tt < beat * d - 0.03)
        out.append(env * (0.22 * np.sign(np.sin(TAU * NOTE[n] * tt)) + 0.12 * np.sin(TAU * NOTE[n] / 2 * tt)))
    out.append(np.zeros(int(sr * 0.8)))
    a = (np.concatenate(out) * 32767).astype("<i2")
    path = os.path.join(tempfile.gettempdir(), "tree_jingle.wav")
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
        start_music(sys.argv[sys.argv.index("--music") + 1] if "--music" in sys.argv else jingle_wav())
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
        p = jingle_wav(); assert os.path.getsize(p) > 100000
        print("ok", (g != " ").sum(), "wav", p); sys.exit()
    main()
