"""Generate original record-sleeve artwork for the purplhrtz catalog.

Photocopied, halftoned, grainy sleeves — one per product, track and project.
Run:  python3 scripts/make_covers.py      (needs numpy + Pillow and `npm install` for the fonts)
Out:  public/media/covers/*.jpg  (1200x1200) and *-sm.jpg (480x480)
Replace any file with a real photo/sleeve of the same name to swap artwork.
"""
from __future__ import annotations

import math
import os
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public", "media", "covers")
F = os.path.join(ROOT, "node_modules", "@fontsource")
ANTON = os.path.join(F, "anton", "files", "anton-latin-400-normal.woff")
MONO = os.path.join(F, "ibm-plex-mono", "files", "ibm-plex-mono-latin-500-normal.woff")
NARROW = os.path.join(F, "archivo-narrow", "files", "archivo-narrow-latin-700-normal.woff")
os.makedirs(OUT, exist_ok=True)
S = 1200

PAPER = (222, 214, 200)
INK = (22, 18, 26)
PLUM = (88, 36, 104)
VIOLET = (128, 72, 220)
TUNGSTEN = (232, 160, 84)
ORANGE = (214, 112, 40)


def font(path, size):
    return ImageFont.truetype(path, size)


def noise(n, scale, seed, power=2.0):
    r = np.random.default_rng(seed)
    w = r.standard_normal((n, n))
    fx = np.fft.fftfreq(n)[:, None]
    fy = np.fft.fftfreq(n)[None, :]
    f = np.sqrt(fx * fx + fy * fy) * n / scale
    f[0, 0] = 1
    o = np.real(np.fft.ifft2(np.fft.fft2(w) / f ** power))
    o -= o.min()
    return o / o.max()


def halftone(gray: np.ndarray, cell=9, angle=15) -> Image.Image:
    """gray 0..1 (1 = paper). Returns L image with dots (0 = ink)."""
    h, w = gray.shape
    big = Image.new("L", (w * 2, h * 2), 255)
    d = ImageDraw.Draw(big)
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    rng = range(-w, 2 * w, cell)
    for gy in rng:
        for gx in rng:
            x = gx * ca - gy * sa
            y = gx * sa + gy * ca
            if 0 <= x < w and 0 <= y < h:
                v = gray[int(y), int(x)]
                r = (1 - v) * cell * 0.72
                if r > 0.4:
                    d.ellipse([2 * (x - r), 2 * (y - r), 2 * (x + r), 2 * (y + r)], fill=0)
    return big.resize((w, h), Image.LANCZOS)


def ink_layer(base: Image.Image, mask: Image.Image, color, offset=(0, 0)) -> Image.Image:
    """Multiply an ink colour through mask (0=ink) with optional misregistration offset."""
    m = ImageChops.offset(mask, *offset)
    layer = Image.new("RGB", base.size, color)
    paper = Image.new("RGB", base.size, (255, 255, 255))
    ink = Image.composite(paper, layer, m)
    return ImageChops.multiply(base, ink)


def finish(im: Image.Image, seed: int, dirt=1.0) -> Image.Image:
    a = np.asarray(im, np.float32) / 255
    r = np.random.default_rng(seed)
    grain = r.normal(0, 0.045, a.shape[:2])[..., None]
    streak = np.clip((noise(S, 300, seed + 9, 0.6) - 0.7) * 2.5, 0, 1)[..., None] * 0.12 * dirt
    toner = (r.random(a.shape[:2]) > 0.9975).astype(np.float32)[..., None] * 0.7 * dirt
    vign = noise(S, 2, seed + 4)[..., None] * 0.18 * dirt
    a = a * (1 - streak) * (1 - toner) * (1 - vign * 0.6) + grain
    # paper fold / worn corner
    yy, xx = np.mgrid[0:S, 0:S] / S
    corner = np.clip(1 - np.hypot(xx - 1, yy - 1) * 6, 0, 1)[..., None] * 0.25 * dirt
    a = a * (1 - corner) + corner * 0.9
    out = Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255))
    return out.filter(ImageFilter.GaussianBlur(0.5))


def paper(color=PAPER, seed=0):
    n = noise(S, 60, seed, 1.2)[..., None]
    base = np.array(color, np.float32)[None, None, :] / 255 * (0.92 + n * 0.1)
    return Image.fromarray(np.uint8(np.clip(base, 0, 1) * 255))


def text(d, xy, s, f, fill=INK, anchor="la", box=None):
    if box:
        bb = d.textbbox(xy, s, font=f, anchor=anchor)
        d.rectangle([bb[0] - box, bb[1] - box, bb[2] + box, bb[3] + box], fill=PAPER)
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def tape(im, x, y, w, h, ang, seed):
    t = Image.new("RGBA", (w, h), (206, 196, 168, 210))
    td = ImageDraw.Draw(t)
    r = random.Random(seed)
    for k in range(0, h, 3):
        td.point([(0, k), (w - 1, k)], fill=(0, 0, 0, 0))
    t = t.rotate(ang, expand=True, resample=Image.BICUBIC)
    im.paste(t, (x, y), t)


def sticker(d, label):
    f = font(MONO, 26)
    d.rectangle([60, S - 110, 60 + 26 * len(label) * 0.62 + 40, S - 62], fill=(20, 18, 22))
    d.text((80, S - 104), label, font=f, fill=(222, 214, 200))


# ------------------------------------------------------------------ designs
def basement_drums():
    im = paper(seed=1)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    # a photographed kick drum head: concentric falloff + hard top-left key light
    r = np.hypot(xx - 640, yy - 700) / 430
    head = np.clip(1 - r, 0, 1)
    light = np.clip(1 - np.hypot(xx - 420, yy - 420) / 900, 0, 1)
    rim = np.exp(-((r - 1.0) / 0.035) ** 2)
    g = 1 - (0.85 - head * 0.55 * light - rim * 0.6) * (r < 1.08) - (r >= 1.08) * 0.08
    g = np.clip(g + noise(S, 20, 2) * 0.12 - 0.06, 0, 1)
    im = ink_layer(im, halftone(g, 10, 22), PLUM, (4, 2))
    im = ink_layer(im, halftone(np.clip(g + 0.35, 0, 1), 10, 67), INK)
    d = ImageDraw.Draw(im)
    text(d, (70, 60), "BASEMENT", font(ANTON, 230), box=10)
    text(d, (70, 330), "DRUMS", font(ANTON, 230), box=10)
    text(d, (S - 70, S - 80), "vol. 1", font(ANTON, 120), anchor="rd", fill=PLUM)
    tape(im, 820, 70, 300, 70, -8, 1)
    sticker(d, "purplhrtz · 120 one-shots")
    return finish(im, 1)


def after_midnight():
    im = Image.new("RGB", (S, S), (14, 12, 18))
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
    # window light falling across a wall: two soft violet bars
    bars = np.exp(-((xx * 1.2 + yy * 0.5 - 0.65) / 0.07) ** 2) + 0.6 * np.exp(-((xx * 1.2 + yy * 0.5 - 0.95) / 0.05) ** 2)
    g = 1 - np.clip(bars * 0.9 + noise(S, 8, 3) * 0.15, 0, 1)
    ht = halftone(g, 8, 45)
    layer = Image.new("RGB", (S, S), VIOLET)
    im = Image.composite(im, layer, ht)
    d = ImageDraw.Draw(im)
    f = font(ANTON, 300)
    txt = Image.new("L", (S, 360), 0)
    ImageDraw.Draw(txt).text((10, 0), "MIDNIGHT", font=f, fill=255)
    txt = txt.rotate(90, expand=True)
    im.paste((222, 214, 200), (S - 380, 0), txt.crop((0, 0, 360, S)))
    d.text((70, 70), "after", font=font(ANTON, 150), fill=(222, 214, 200))
    d.text((74, 250), "48 loops · 80–140 bpm", font=font(MONO, 30), fill=(190, 170, 230))
    d.text((74, S - 140), "02:47", font=font(MONO, 90), fill=TUNGSTEN)
    return finish(im, 2, 0.7)


def bruised_plum():
    im = paper((216, 206, 196), seed=5)
    g = noise(S, 3.5, 6) * 0.7 + noise(S, 14, 7, 1.5) * 0.3
    bruise = np.clip((g - 0.35) * 2.2, 0, 1)
    im = ink_layer(im, halftone(1 - bruise * 0.95, 7, 30), PLUM, (0, 0))
    im = ink_layer(im, halftone(1 - np.clip((g - 0.62) * 3.5, 0, 1), 7, 75), VIOLET, (6, -4))
    im = ink_layer(im, halftone(1 - np.clip((g - 0.78) * 4, 0, 1) * 0.8, 7, 5), INK, (-3, 3))
    d = ImageDraw.Draw(im)
    text(d, (70, S - 360), "bruised", font(ANTON, 150), box=8)
    text(d, (70, S - 210), "plum", font(ANTON, 150), box=8, fill=PLUM)
    text(d, (S - 70, 80), "64 PATCHES", font(MONO, 34), anchor="ra", box=6)
    text(d, (S - 70, 130), "12 MULTISAMPLES", font(MONO, 34), anchor="ra", box=6)
    return finish(im, 3)


def night_shift():
    im = paper((196, 190, 182), seed=8)
    g = 1 - np.clip(noise(S, 4, 9) * 1.4 - 0.3, 0, 1)
    im = ink_layer(im, halftone(g, 12, 45), INK)
    d = ImageDraw.Draw(im)
    text(d, (S // 2, 140), "NIGHT SHIFT", font(ANTON, 190), anchor="mt", box=12)
    text(d, (S // 2, 380), "sessions · 11pm–4am", font(MONO, 40), anchor="mt", box=8)
    tape(im, 60, 40, 260, 64, 12, 3)
    tape(im, 880, 1050, 260, 64, -6, 4)
    return finish(im, 4)


def tape_swap():
    im = paper(seed=10)
    d = ImageDraw.Draw(im)
    r = random.Random(4)
    for k in range(7):
        x, y = 120 + r.randint(-40, 600), 300 + r.randint(-80, 600)
        ang = r.uniform(-25, 25)
        c = Image.new("RGBA", (420, 270), (0, 0, 0, 0))
        cd = ImageDraw.Draw(c)
        cd.rounded_rectangle([0, 0, 419, 269], 18, fill=(30, 26, 34, 255))
        cd.rectangle([40, 30, 380, 130], fill=(206, 196, 168, 255))
        cd.text((56, 52), r.choice(["side a", "mix 4", "do not tape over", "room tone", "demo?"]), font=font(MONO, 30), fill=INK)
        for cx in (130, 290):
            cd.ellipse([cx - 40, 160, cx + 40, 240], fill=(200, 190, 170, 255))
            cd.ellipse([cx - 14, 186, cx + 14, 214], fill=(30, 26, 34, 255))
        c = c.rotate(ang, expand=True, resample=Image.BICUBIC)
        im.paste(c, (x, y), c)
    text(d, (70, 60), "TAPE SWAP", font(ANTON, 200), box=10)
    text(d, (76, 290), "ep · 4 songs", font(MONO, 36), box=6, fill=PLUM)
    return finish(im, 5)


def hum():
    im = Image.new("RGB", (S, S), (24, 22, 26))
    d = ImageDraw.Draw(im)
    for k in range(9):
        y0 = 160 + k * 110
        pts = [(x, y0 + 28 * math.sin(x / 70 + k * 0.6) * math.exp(-((x - 600) / 420) ** 2)) for x in range(0, S, 6)]
        d.line(pts, fill=(170 - k * 8, 150 - k * 10, 210), width=3)
    d.text((70, 60), "hum", font=font(ANTON, 260), fill=(222, 214, 200))
    d.text((74, S - 120), "original score · 11 min", font=font(MONO, 34), fill=(180, 170, 200))
    return finish(im, 6, 0.6)


def low_ceiling():
    im = Image.new("RGB", (S, S), (18, 16, 20))
    d = ImageDraw.Draw(im)
    vp = (S * 0.55, S * 0.62)
    for k in range(-10, 11):
        x = S / 2 + k * 160
        d.line([(x, 0), vp], fill=(60, 54, 66), width=max(2, 14 - abs(k)))
    for k in range(1, 14):
        y = vp[1] * (1 - 0.82 ** k)
        d.line([(0, y), (S, y)], fill=(44, 40, 50), width=3)
    d.ellipse([vp[0] - 40, vp[1] - 40, vp[0] + 40, vp[1] + 40], fill=TUNGSTEN)
    glow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(glow).ellipse([vp[0] - 220, vp[1] - 220, vp[0] + 220, vp[1] + 220], fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    im = Image.composite(Image.new("RGB", (S, S), TUNGSTEN), im, glow.point(lambda v: v * 0.5))
    d = ImageDraw.Draw(im)
    d.text((70, S - 390), "low", font=font(ANTON, 150), fill=(222, 214, 200))
    d.text((70, S - 240), "ceiling", font=font(ANTON, 150), fill=(222, 214, 200))
    return finish(im, 7, 0.7)


def barrys_4am():
    im = paper((206, 196, 180), seed=12)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    # a sleeping orange cat, as a halftoned photo: curled body + head + ear triangles
    body = np.exp(-(((xx - 620) / 330) ** 2 + ((yy - 720) / 210) ** 2) ** 1.5)
    head = np.exp(-(((xx - 330) / 140) ** 2 + ((yy - 760) / 120) ** 2) ** 1.5)
    ears = np.zeros_like(body)
    for ex, ey in ((270, 620), (380, 610)):
        ears += ((np.abs(xx - ex) < (ey + 40 - yy) * 0.6) & (yy < ey + 40) & (yy > ey - 40)).astype(np.float32)
    shape = np.clip(body + head + ears, 0, 1)
    stripes = (np.sin((xx * 0.035) + noise(S, 6, 13) * 5) * 0.5 + 0.5)
    tone = shape * (0.72 + stripes * 0.16) * (0.85 + 0.15 * (yy < 700))
    light = np.clip(1 - np.hypot(xx - 300, yy - 300) / 1100, 0, 1)
    g = 1 - np.clip(tone * (0.6 + light * 0.6) + noise(S, 30, 14) * 0.08, 0, 1)
    im = ink_layer(im, halftone(g, 9, 15), ORANGE, (5, 3))
    im = ink_layer(im, halftone(np.clip(g + 0.4, 0, 1), 9, 75), INK)
    d = ImageDraw.Draw(im)
    text(d, (70, 70), "barry's", font(ANTON, 170), box=8)
    text(d, (70, 270), "4am", font(ANTON, 170), box=8, fill=PLUM)
    sticker(d, "purr: left channel")
    return finish(im, 8)


def cinder():
    im = paper((60, 54, 66), seed=15)
    d = ImageDraw.Draw(im)
    for row in range(8):
        off = (row % 2) * 150
        for col in range(-1, 5):
            x = col * 300 + off
            y = row * 150
            v = random.Random(row * 10 + col).randint(-10, 10)
            d.rectangle([x + 8, y + 8, x + 292, y + 142], fill=(84 + v, 76 + v, 92 + v))
    im = Image.blend(im, Image.new("RGB", (S, S), PLUM), 0.25)
    d = ImageDraw.Draw(im)
    text(d, (S // 2, S // 2), "cinder", font(ANTON, 300), anchor="mm", box=18)
    text(d, (S // 2, S // 2 + 190), "demo", font(MONO, 40), anchor="mm", box=6)
    return finish(im, 9)


if __name__ == "__main__":
    jobs = {
        "basement-drums": basement_drums, "after-midnight": after_midnight, "bruised-plum": bruised_plum,
        "night-shift": night_shift, "tape-swap": tape_swap, "hum": hum,
        "low-ceiling": low_ceiling, "barrys-4am": barrys_4am, "cinder": cinder,
    }
    for name, fn in jobs.items():
        im = fn()
        im.save(os.path.join(OUT, f"{name}.jpg"), quality=86, optimize=True, progressive=True)
        im.resize((480, 480), Image.LANCZOS).save(os.path.join(OUT, f"{name}-sm.jpg"), quality=84, optimize=True)
        print(name)
