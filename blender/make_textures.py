"""Procedural, tileable PBR textures for the purplhrtz basement.

Everything here is generated from noise so the set is original and license-free.
Run with:  /opt/bpyenv/bin/python blender/make_textures.py
Outputs:   blender/textures/<name>_{albedo,rough,normal}.png
"""
from __future__ import annotations

import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "textures")
FONTS = os.path.join(ROOT, "..", "node_modules", "@fontsource")
ANTON = os.path.join(FONTS, "anton", "files", "anton-latin-400-normal.woff")
MONO = os.path.join(FONTS, "ibm-plex-mono", "files", "ibm-plex-mono-latin-500-normal.woff")
NARROW = os.path.join(FONTS, "archivo-narrow", "files", "archivo-narrow-latin-700-normal.woff")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(1337)
random.seed(1337)


# ------------------------------------------------------------------ helpers
def fnoise(n: int, scale: float, seed: int, power: float = 2.0) -> np.ndarray:
    """Periodic fractal noise via filtered FFT (tiles seamlessly)."""
    r = np.random.default_rng(seed)
    white = r.standard_normal((n, n))
    fx = np.fft.fftfreq(n)[:, None]
    fy = np.fft.fftfreq(n)[None, :]
    f = np.sqrt(fx * fx + fy * fy) * n / max(scale, 1e-3)
    f[0, 0] = 1.0
    spec = np.fft.fft2(white) / (f ** power)
    spec[0, 0] = 0
    out = np.real(np.fft.ifft2(spec))
    out -= out.min()
    out /= max(out.max(), 1e-9)
    return out


def blur(a: np.ndarray, r: float) -> np.ndarray:
    im = Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), dtype=np.float32) / 255


def normal_from_height(h: np.ndarray, strength: float) -> np.ndarray:
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * strength
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * strength
    nz = np.ones_like(h)
    n = np.stack([-dx, dy, nz], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return (n * 0.5 + 0.5)


def save(name: str, arr: np.ndarray, kind: str) -> None:
    a = np.clip(arr, 0, 1)
    if a.ndim == 2:
        im = Image.fromarray(np.uint8(a * 255), "L")
    else:
        im = Image.fromarray(np.uint8(a * 255), "RGB")
    im.save(os.path.join(OUT, f"{name}_{kind}.png"), optimize=True)


def srgb(hexstr: str) -> np.ndarray:
    h = hexstr.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


def tint(gray: np.ndarray, lo: str, hi: str) -> np.ndarray:
    a, b = srgb(lo), srgb(hi)
    return a[None, None, :] * (1 - gray[..., None]) + b[None, None, :] * gray[..., None]


def scratches(n: int, count: int, seed: int, maxlen: float = 0.25, width: int = 1) -> np.ndarray:
    r = random.Random(seed)
    im = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(im)
    for _ in range(count):
        x, y = r.random() * n, r.random() * n
        ang = r.gauss(0.3, 0.6)
        ln = r.random() * maxlen * n
        pts = []
        for k in range(6):
            t = k / 5
            pts.append((x + math.cos(ang + r.gauss(0, 0.03)) * ln * t, y + math.sin(ang) * ln * t))
        d.line(pts, fill=int(80 + r.random() * 175), width=width)
    a = np.asarray(im, dtype=np.float32) / 255
    # wrap by tiling 3x3 then crop: cheap seam fix
    big = np.tile(a, (3, 3))
    return np.maximum(a, big[n:2 * n, n:2 * n])


# ------------------------------------------------------------------ concrete floor
def concrete(n=1024):
    base = fnoise(n, 6, 1) * 0.55 + fnoise(n, 40, 2, 1.6) * 0.3 + fnoise(n, 200, 3, 1.0) * 0.15
    stains = np.clip((fnoise(n, 3, 4) - 0.55) * 3.0, 0, 1)
    pits = (rng.random((n, n)) > 0.9965).astype(np.float32)
    pits = blur(pits, 0.8) * 3
    scuff = scratches(n, 180, 5, 0.12)
    g = base * 0.55 + 0.25 - stains * 0.18 - np.clip(pits, 0, 1) * 0.25 + scuff * 0.08
    albedo = tint(np.clip(g, 0, 1), "#17161a", "#5d5a5c")
    rough = np.clip(0.78 + fnoise(n, 10, 6) * 0.15 - stains * 0.25 - scuff * 0.1, 0.35, 1)
    h = base * 0.4 - np.clip(pits, 0, 1) * 0.6 + fnoise(n, 300, 7, 0.8) * 0.2
    save("concrete", albedo, "albedo"); save("concrete", rough, "rough")
    save("concrete", normal_from_height(h, 2.5), "normal")


# ------------------------------------------------------------------ painted cinder block
def cinderblock(n=1024):
    # tile = 2 blocks wide x 4 courses (each block 400 x 200 mm incl. mortar) => 0.8m square
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n
    course = np.floor(y * 4)
    xo = (x + (course % 2) * 0.25) % 1.0
    bx = (xo * 2) % 1.0
    by = (y * 4) % 1.0
    mw = 0.022
    mortar_x = np.minimum(bx, 1 - bx) < mw * 0.5 * 2
    mortar_y = np.minimum(by, 1 - by) < mw * 2
    mortar = (mortar_x | mortar_y).astype(np.float32)
    mortar = blur(mortar, 1.2)
    pores = fnoise(n, 260, 11, 0.6)
    pores = np.clip((pores - 0.62) * 4, 0, 1)
    paint_var = fnoise(n, 5, 12) * 0.5 + fnoise(n, 60, 13, 1.4) * 0.5
    drips = np.clip((fnoise(n, 30, 14) - 0.7) * 5, 0, 1) * (np.sin(x * 140) > 0.96)
    scuff = scratches(n, 60, 15, 0.08, 2) * (y > 0.7)
    g = 0.55 + paint_var * 0.25 - mortar * 0.22 - pores * 0.25 - scuff * 0.15 + drips * 0.05
    albedo = tint(np.clip(g, 0, 1), "#1e1b22", "#575060")
    rough = np.clip(0.72 + pores * 0.2 + mortar * 0.15 - paint_var * 0.1, 0, 1)
    h = (1 - mortar) * 0.6 - pores * 0.25 + fnoise(n, 120, 16, 1.0) * 0.15
    save("cinder", albedo, "albedo"); save("cinder", rough, "rough")
    save("cinder", normal_from_height(blur(h, 0.7), 6), "normal")


# ------------------------------------------------------------------ fabrics
def weave(n, freq, seed):
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n
    w1 = (np.sin(x * math.tau * freq) * 0.5 + 0.5)
    w2 = (np.sin(y * math.tau * freq) * 0.5 + 0.5)
    checker = (np.floor(x * freq * 2) + np.floor(y * freq * 2)) % 2
    return w1 * checker + w2 * (1 - checker), fnoise(n, 30, seed, 1.2)


def fabric(name, lo, hi, n=512, freq=96, wear=0.0, seed=20):
    wv, nz = weave(n, freq, seed)
    pill = fnoise(n, 120, seed + 1, 0.9)
    worn = np.clip((fnoise(n, 3, seed + 2) - (1 - wear)) * 3, 0, 1) if wear else 0
    g = 0.35 + wv * 0.25 + nz * 0.3 + pill * 0.1 + worn * 0.2
    save(name, tint(np.clip(g, 0, 1), lo, hi), "albedo")
    save(name, np.clip(0.92 - wv * 0.06, 0, 1), "rough")
    save(name, normal_from_height(wv * 0.5 + pill * 0.3, 3), "normal")


def knit(n=512):
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n
    cols = 24
    cx = (x * cols) % 1.0
    v = np.abs(((y * cols * 1.4 + np.abs(cx - 0.5) * 1.2) % 1.0) - 0.5) * 2
    cable = np.clip(1 - np.abs(cx - 0.5) * 2.2, 0, 1)
    h = v * 0.6 + cable * 0.3 + fnoise(n, 80, 30, 1.0) * 0.2
    g = 0.55 + h * 0.3 + fnoise(n, 4, 31) * 0.15
    save("blanket", tint(np.clip(g, 0, 1), "#4d4741", "#aaa092"), "albedo")
    save("blanket", np.full((n, n), 0.95), "rough")
    save("blanket", normal_from_height(blur(h, 0.6), 5), "normal")


# ------------------------------------------------------------------ wood
def wood(name, lo, hi, n=1024, wear=True, seed=40):
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n
    warp = fnoise(n, 4, seed) * 2.5 + fnoise(n, 20, seed + 1, 1.5) * 0.4
    rings = np.sin((y * 34 + warp) * math.tau) * 0.5 + 0.5
    rings = rings ** 3
    fibers = fnoise(n, 400, seed + 2, 0.7)
    fibers = np.asarray(Image.fromarray(np.uint8(fibers * 255)).resize((n * 8, n // 8)).resize((n, n)), np.float32) / 255
    g = 0.45 + rings * 0.25 + fibers * 0.2 + fnoise(n, 3, seed + 3) * 0.15
    sc = scratches(n, 260, seed + 4, 0.1)
    ring_marks = np.zeros((n, n), np.float32)
    if wear:
        im = Image.new("L", (n, n), 0)
        d = ImageDraw.Draw(im)
        for cx, cy, r in [(0.3, 0.42, 0.06), (0.71, 0.6, 0.05)]:
            d.ellipse([(cx - r) * n, (cy - r) * n, (cx + r) * n, (cy + r) * n], outline=120, width=3)
        ring_marks = blur(np.asarray(im, np.float32) / 255, 2)
    g = g + sc * 0.18 - ring_marks * 0.2
    save(name, tint(np.clip(g, 0, 1), lo, hi), "albedo")
    save(name, np.clip(0.55 - rings * 0.1 + sc * 0.25 + ring_marks * 0.2 + fnoise(n, 8, seed + 5) * 0.15, 0, 1), "rough")
    save(name, normal_from_height(rings * 0.2 + fibers * 0.4 - sc * 0.3, 2.0), "normal")


# ------------------------------------------------------------------ metal
def metal(name, lo, hi, n=512, seed=60, count=500):
    brushed = fnoise(n, 300, seed, 0.6)
    brushed = np.asarray(Image.fromarray(np.uint8(brushed * 255)).resize((n * 16, n // 16)).resize((n, n)), np.float32) / 255
    sc = scratches(n, count, seed + 1, 0.15)
    chips = np.clip((fnoise(n, 60, seed + 2, 1.3) - 0.8) * 6, 0, 1)
    g = 0.4 + brushed * 0.25 + sc * 0.45 + chips * 0.4
    save(name, tint(np.clip(g, 0, 1), lo, hi), "albedo")
    save(name, np.clip(0.42 + brushed * 0.15 - sc * 0.2 + chips * 0.3, 0, 1), "rough")
    save(name, normal_from_height(brushed * 0.2 - sc * 0.5, 2), "normal")


# ------------------------------------------------------------------ cork
def cork(n=512):
    a = fnoise(n, 180, 70, 0.7) * 0.6 + fnoise(n, 30, 71, 1.3) * 0.4
    dots = np.clip((fnoise(n, 260, 72, 0.4) - 0.6) * 4, 0, 1)
    pins = np.zeros((n, n), np.float32)
    for _ in range(120):  # old pin holes
        px, py = rng.integers(0, n, 2)
        pins[py, px] = 1
    pins = blur(pins, 1.0) * 4
    g = 0.5 + a * 0.4 - dots * 0.3 - np.clip(pins, 0, 1) * 0.4
    save("cork", tint(np.clip(g, 0, 1), "#3a2516", "#a37a52"), "albedo")
    save("cork", np.full((n, n), 0.9), "rough")
    save("cork", normal_from_height(a - dots, 3), "normal")


# ------------------------------------------------------------------ rug
def rug(n=1024):
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n
    diamond = (np.abs((x * 6) % 1 - 0.5) + np.abs((y * 4) % 1 - 0.5))
    band = (np.abs(y - 0.5) > 0.42).astype(np.float32)
    pattern = ((diamond > 0.38) & (diamond < 0.46)).astype(np.float32)
    fade = fnoise(n, 3, 80) * 0.6
    wv, nz = weave(n, 200, 81)
    base = tint(nz * 0.3 + 0.4, "#1c1420", "#3a2738")
    accent = tint(nz * 0.2 + 0.5, "#5b4a52", "#a5958e")
    m = np.clip(pattern + band * 0.6, 0, 1)[..., None] * (1 - fade[..., None] * 0.6)
    col = base * (1 - m) + accent * m
    col *= (0.85 + wv[..., None] * 0.15)
    save("rug", col, "albedo")
    save("rug", np.full((n, n), 0.97), "rough")
    save("rug", normal_from_height(wv * 0.5 + nz * 0.3, 2), "normal")


# ------------------------------------------------------------------ leather-ish couch
def couch(n=512):
    grain = fnoise(n, 220, 90, 0.8)
    cracks = np.clip((fnoise(n, 50, 91, 1.2) - 0.72) * 5, 0, 1)
    wear = fnoise(n, 3, 92)
    g = 0.4 + grain * 0.2 + wear * 0.25 + cracks * 0.25
    save("couch", tint(np.clip(g, 0, 1), "#140f12", "#4a3a3c"), "albedo")
    save("couch", np.clip(0.55 + grain * 0.15 + cracks * 0.3 - wear * 0.1, 0, 1), "rough")
    save("couch", normal_from_height(grain * 0.3 - cracks * 0.6, 3), "normal")


# ------------------------------------------------------------------ plastic / gear shells
def plastic(name, lo, hi, n=256, seed=100):
    g = fnoise(n, 80, seed, 1.0) * 0.4 + 0.4 + scratches(n, 40, seed + 1, 0.2) * 0.3
    save(name, tint(np.clip(g, 0, 1), lo, hi), "albedo")
    save(name, np.clip(0.45 + fnoise(n, 20, seed + 2) * 0.2, 0, 1), "rough")


# ------------------------------------------------------------------ printed decals
def tape_label():
    w, h = 1024, 160
    im = Image.new("RGB", (w, h), (198, 186, 160))
    a = np.asarray(im, np.float32) / 255
    nz = fnoise(1024, 20, 110)[:h, :w]
    a = a * (0.86 + nz[..., None] * 0.2)
    # torn ends
    mask = np.ones((h, w), np.float32)
    for side in (0, 1):
        for yy in range(h):
            cut = int(14 + 10 * math.sin(yy * 0.37) + random.random() * 12)
            if side == 0:
                mask[yy, :cut] = 0
            else:
                mask[yy, w - cut:] = 0
    im = Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(ANTON, 118)
    d.text((70, 10), "purplhrtz", font=f, fill=(34, 24, 40))
    f2 = ImageFont.truetype(MONO, 30)
    d.text((640, 64), "MAIN BUS / B", font=f2, fill=(80, 40, 90))
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    out = np.asarray(im, np.float32) / 255
    out = out * mask[..., None] + np.array([0.06, 0.05, 0.06]) * (1 - mask[..., None])
    Image.fromarray(np.uint8(np.clip(out, 0, 1) * 255)).save(os.path.join(OUT, "tape_purplhrtz_albedo.png"))
    # small generic tape labels for the rack / desk
    labels = ["VOX 1", "KICK", "TALKBACK", "DO NOT TOUCH", "BASS DI", "SYNTH L/R", "CUE", "LAMP"]
    sheet = Image.new("RGB", (1024, 512), (190, 178, 150))
    d = ImageDraw.Draw(sheet)
    fm = ImageFont.truetype(MONO, 44)
    for i, t in enumerate(labels):
        x0, y0 = (i % 2) * 512, (i // 2) * 128
        shade = 150 + int(random.random() * 60)
        d.rectangle([x0, y0, x0 + 511, y0 + 127], fill=(shade, shade - 12, shade - 40))
        d.text((x0 + 30, y0 + 36), t, font=fm, fill=(40, 30, 50))
    sheet = sheet.filter(ImageFilter.GaussianBlur(0.8))
    sheet.save(os.path.join(OUT, "tape_labels_albedo.png"))


def halftone(im: Image.Image, cell=6) -> Image.Image:
    g = im.convert("L")
    w, h = g.size
    out = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(out)
    px = g.load()
    for yy in range(0, h, cell):
        for xx in range(0, w, cell):
            v = px[min(xx + cell // 2, w - 1), min(yy + cell // 2, h - 1)] / 255
            r = (1 - v) * cell * 0.75
            if r > 0.3:
                d.ellipse([xx + cell / 2 - r, yy + cell / 2 - r, xx + cell / 2 + r, yy + cell / 2 + r], fill=0)
    return out


def flyer(name, lines, ink, paper=(214, 206, 192), seed=0):
    w, h = 600, 840
    r = random.Random(seed)
    # photo-ish blob background, halftoned
    n = fnoise(1024, 3, 200 + seed)[:h, :w]
    n2 = fnoise(1024, 12, 210 + seed, 1.4)[:h, :w]
    photo = Image.fromarray(np.uint8(np.clip((n * 0.7 + n2 * 0.3) ** 1.6, 0, 1) * 255))
    ht = halftone(photo, 7)
    base = Image.new("RGB", (w, h), paper)
    inkimg = Image.new("RGB", (w, h), ink)
    base = Image.composite(base, inkimg, ht)
    d = ImageDraw.Draw(base)
    y = 40
    for text, size, font in lines:
        f = ImageFont.truetype(font, size)
        bb = d.textbbox((0, 0), text, font=f)
        tw = bb[2] - bb[0]
        x = (w - tw) // 2 + r.randint(-8, 8)
        d.rectangle([x - 10, y - 4, x + tw + 10, y + (bb[3] - bb[1]) + bb[1] + 10], fill=paper)
        d.text((x, y), text, font=f, fill=(18, 14, 20))
        y += (bb[3]) + 22
    # photocopy grit
    a = np.asarray(base, np.float32) / 255
    grit = (rng.random((h, w)) > 0.994).astype(np.float32)
    streak = np.clip((fnoise(1024, 200, 220 + seed, 0.5)[:h, :w] - 0.75) * 3, 0, 1)
    a = a * (1 - grit[..., None] * 0.8) * (1 - streak[..., None] * 0.15)
    yellow = np.array([1.0, 0.95, 0.82])
    a = a * yellow
    Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255)).filter(ImageFilter.GaussianBlur(0.5)).save(
        os.path.join(OUT, f"{name}_albedo.png"))


def rack_faces():
    """Faceplates for the 19" gear rack: 6 x 1U/2U units with knobs, meters, scratches."""
    w, h = 1024, 768
    im = Image.new("RGB", (w, h), (18, 17, 20))
    d = ImageDraw.Draw(im)
    units = [(0, 128, "PRE-2", (26, 24, 28)), (128, 256, "COMP", (40, 36, 44)),
             (256, 320, "PATCHBAY", (22, 21, 24)), (320, 448, "TAPE ECHO", (58, 48, 40)),
             (448, 576, "EQ 4K", (30, 30, 34)), (576, 768, "POWER", (20, 20, 22))]
    fm = ImageFont.truetype(MONO, 22)
    fl = ImageFont.truetype(NARROW, 30)
    for i, (y0, y1, label, col) in enumerate(units):
        d.rectangle([0, y0 + 2, w, y1 - 2], fill=col)
        for sx in (20, w - 20):  # rack screws
            for sy in (y0 + 18, y1 - 18):
                d.ellipse([sx - 8, sy - 8, sx + 8, sy + 8], fill=(120, 118, 115))
                d.line([sx - 5, sy, sx + 5, sy], fill=(50, 50, 50), width=2)
        d.text((60, y0 + 14), label, font=fl, fill=(200, 192, 180))
        if label == "PATCHBAY":
            for k in range(24):
                x = 70 + k * 37
                d.ellipse([x, y0 + 22, x + 16, y0 + 38], fill=(8, 8, 8))
                d.ellipse([x, y0 + 44, x + 16, y0 + 60], fill=(8, 8, 8))
            continue
        nk = 6 if (y1 - y0) >= 128 else 4
        for k in range(nk):
            cx = 260 + k * 110
            cy = (y0 + y1) // 2 + 6
            d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(14, 14, 16), outline=(90, 88, 92), width=2)
            ang = random.random() * 4 - 2
            d.line([cx, cy, cx + math.sin(ang) * 22, cy - math.cos(ang) * 22], fill=(220, 214, 200), width=3)
        if label in ("COMP", "TAPE ECHO"):
            d.rectangle([w - 220, y0 + 24, w - 70, y1 - 24], fill=(190, 160, 90))
            d.arc([w - 200, y0 + 40, w - 90, y1 + 10], 200, 340, fill=(30, 20, 10), width=2)
        d.ellipse([w - 52, y0 + 30, w - 38, y0 + 44], fill=(150, 60, 200) if i % 2 else (240, 140, 50))
        # faded tape label
        lx = 120 + random.randint(0, 400)
        d.rectangle([lx, y1 - 34, lx + 150, y1 - 8], fill=(170, 160, 132))
        d.text((lx + 10, y1 - 32), random.choice(["VOX", "DRUMS", "SYN", "8-TRK", "BUS B", "KEEP"]), font=fm, fill=(60, 50, 60))
    a = np.asarray(im, np.float32) / 255
    sc = scratches(1024, 300, 300, 0.2)[:h, :w]
    a = a + sc[..., None] * 0.18
    Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255)).save(os.path.join(OUT, "rack_faces_albedo.png"))


def midi_top():
    w, h = 1024, 256
    im = Image.new("RGB", (w, h), (22, 22, 25))
    d = ImageDraw.Draw(im)
    for k in range(8):  # pads
        x = 40 + k * 60
        d.rounded_rectangle([x, 40, x + 50, 90], 6, fill=(48, 44, 52))
        d.rounded_rectangle([x, 110, x + 50, 160], 6, fill=(48, 44, 52))
    for k in range(8):  # knobs
        cx = 560 + k * 55
        d.ellipse([cx - 18, 60, cx + 18, 96], fill=(10, 10, 12), outline=(70, 70, 75))
        d.line([cx, 78, cx + 10, 64], fill=(230, 220, 210), width=2)
    for k in range(8):  # faders
        x = 560 + k * 55
        d.rectangle([x - 2, 120, x + 2, 210], fill=(5, 5, 5))
        fy = 130 + random.randint(0, 70)
        d.rectangle([x - 12, fy, x + 12, fy + 14], fill=(160, 156, 150))
    fm = ImageFont.truetype(MONO, 18)
    d.text((40, 200), "pad bank A    oct -1  +1", font=fm, fill=(140, 135, 130))
    a = np.asarray(im, np.float32) / 255 + scratches(1024, 80, 310, 0.2)[:h, :w, None] * 0.1
    Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255)).save(os.path.join(OUT, "midi_top_albedo.png"))


def lamp_shade():
    plastic("lampshade", "#14120f", "#3a342c", seed=120)


if __name__ == "__main__":
    concrete(); print("concrete")
    cinderblock(); print("cinder")
    fabric("acoustic", "#141216", "#38323b", freq=110, seed=20); print("acoustic")
    fabric("acoustic_plum", "#1d1220", "#4b3150", freq=110, wear=0.2, seed=24); print("acoustic plum")
    knit(); print("blanket")
    wood("desk", "#1d130d", "#5a3d29", seed=40); print("desk")
    wood("stairs", "#221c19", "#615448", wear=False, seed=44); print("stairs")
    metal("rack", "#0e0e10", "#4a4850", seed=60); print("rack")
    metal("steel", "#2a2a2d", "#8a8a90", seed=64, count=200); print("steel")
    cork(); print("cork")
    rug(); print("rug")
    couch(); print("couch")
    plastic("plastic_black", "#0b0b0c", "#2a2a2e", seed=100)
    plastic("plastic_grey", "#3a3a3e", "#77777d", seed=104)
    lamp_shade()
    tape_label()
    flyer("flyer_a", [("NIGHT SHIFT", 96, ANTON), ("purplhrtz", 72, ANTON), ("basement session", 34, MONO),
                      ("FRI 11.14  /  DOORS 11PM", 30, NARROW)], ink=(92, 38, 128), seed=1)
    flyer("flyer_b", [("LOW END", 110, ANTON), ("THEORY", 110, ANTON), ("w/ purplhrtz + friends", 30, MONO),
                      ("no cover  //  bring earplugs", 28, NARROW)], ink=(30, 28, 34), seed=2)
    flyer("flyer_c", [("TAPE", 130, ANTON), ("SWAP", 130, ANTON), ("sat 2pm · back room", 32, MONO)],
          ink=(140, 60, 70), paper=(200, 196, 186), seed=3)
    rack_faces(); midi_top()
    print("done")
