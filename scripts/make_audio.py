"""Original, synthesized audio for the purplhrtz demo (no samples, no third-party material).

Run:  python3 scripts/make_audio.py   (numpy + ffmpeg)
Out:  public/media/audio/*.mp3  — three 32s track previews + three product previews
      public/media/sfx/*.mp3    — room tone loop, lamp click, laptop startup, purrs
      private-downloads/*.zip   — small stand-in bundles for the paid downloads

Replace any file with a real purplhrtz bounce of the same name to swap it in.
"""
from __future__ import annotations

import io
import math
import os
import subprocess
import wave
import zipfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, "public", "media", "audio")
SFX = os.path.join(ROOT, "public", "media", "sfx")
DL = os.path.join(ROOT, "private-downloads")
for d in (AUD, SFX, DL):
    os.makedirs(d, exist_ok=True)
SR = 44100
rng = np.random.default_rng(42)


# ------------------------------------------------------------------ dsp helpers
def t(sec):
    return np.arange(int(sec * SR)) / SR


def env_exp(n, decay):
    return np.exp(-np.arange(n) / SR / decay)


def onepole_lp(x, fc):
    a = math.exp(-2 * math.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    # vectorised via lfilter-like recursion in chunks would be faster; this is fine for our lengths
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def fft_filter(x, lo=None, hi=None, slope=2.0):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if hi:
        g /= 1 + (f / hi) ** (2 * slope)
    if lo:
        g /= 1 + (lo / np.maximum(f, 1e-3)) ** (2 * slope)
    return np.fft.irfft(X * g, len(x))


def reverb(x, seconds=1.4, mix=0.25, seed=1, damp=4000):
    n = int(seconds * SR)
    r = np.random.default_rng(seed)
    ir = r.standard_normal(n) * np.exp(-np.arange(n) / SR / (seconds / 6.9))
    ir = fft_filter(ir, hi=damp)
    ir /= np.sqrt(np.sum(ir ** 2))
    L = len(x) + n
    nfft = 1 << (L - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]
    return x * (1 - mix) + wet * mix


def tape(x, wow=0.0018, sat=1.6, hiss=0.004, seed=3):
    n = len(x)
    tt = np.arange(n) / SR
    mod = wow * SR * (np.sin(2 * np.pi * 0.55 * tt) + 0.4 * np.sin(2 * np.pi * 6.1 * tt + 1))
    idx = np.clip(np.arange(n) - 200 + mod, 0, n - 1)
    y = np.interp(idx, np.arange(n), x)
    y = np.tanh(y * sat) / np.tanh(sat)
    y = fft_filter(y, hi=11000)
    return y + np.random.default_rng(seed).standard_normal(n) * hiss


def place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def mtof(m):
    return 440 * 2 ** ((m - 69) / 12)


# ------------------------------------------------------------------ instruments
def kick(tone=1.0, decay=0.42):
    n = int(0.7 * SR)
    tt = np.arange(n) / SR
    f = 42 * tone + 95 * np.exp(-tt / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-tt / decay)
    s += rng.standard_normal(n) * np.exp(-tt / 0.004) * 0.25
    return np.tanh(s * 1.8)


def snare(decay=0.18, tone=185):
    n = int(0.5 * SR)
    tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * tone * tt) * np.exp(-tt / 0.06)
    nz = fft_filter(rng.standard_normal(n), lo=1500, hi=9000) * np.exp(-tt / decay)
    return np.tanh((body * 0.6 + nz * 1.1) * 1.4)


def rim():
    n = int(0.12 * SR)
    tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 820 * tt) + 0.5 * np.sin(2 * np.pi * 1700 * tt)) * np.exp(-tt / 0.018)


def hat(decay=0.035, open_=False):
    n = int((0.4 if open_ else 0.12) * SR)
    tt = np.arange(n) / SR
    nz = fft_filter(rng.standard_normal(n), lo=7000, hi=15000)
    return nz * np.exp(-tt / (0.18 if open_ else decay)) * 0.7


def bass(m, dur, glide_from=None):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = np.full(n, mtof(m))
    if glide_from is not None:
        f = mtof(m) + (mtof(glide_from) - mtof(m)) * np.exp(-tt / 0.06)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) + 0.18 * np.sin(2 * ph)
    e = np.minimum(1, tt / 0.01) * np.exp(-tt / (dur * 0.9))
    return np.tanh(s * e * 1.5) * 0.9


def pad(chord, dur, bright=1800, detune=0.12):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    s = np.zeros(n)
    for m in chord:
        for d in (-detune, 0, detune):
            f = mtof(m + d)
            ph = (tt * f + rng.random()) % 1.0
            s += (2 * ph - 1) * 0.12
    s = fft_filter(s, hi=bright, slope=1.5)
    a = np.minimum(1, tt / 0.9) * np.minimum(1, (dur - tt) / 1.0).clip(0, 1)
    return s * a


def epiano(m, dur, vel=1.0):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = mtof(m)
    mod = np.sin(2 * np.pi * f * 14 * tt) * 1.6 * np.exp(-tt / 0.25)
    s = np.sin(2 * np.pi * f * tt + mod) * np.exp(-tt / 1.6)
    s += 0.3 * np.sin(2 * np.pi * f * 2 * tt) * np.exp(-tt / 0.6)
    return s * vel * 0.32


def pluck(m, dur=0.5):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = mtof(m)
    s = np.sign(np.sin(2 * np.pi * f * tt)) * 0.4 + np.sin(2 * np.pi * f * tt) * 0.6
    s = fft_filter(s, hi=2600) * np.exp(-tt / 0.16)
    return s * 0.35


def purr_noise(sec, rate=26.0, seed=7):
    n = int(sec * SR)
    tt = np.arange(n) / SR
    r = np.random.default_rng(seed)
    base = fft_filter(r.standard_normal(n), lo=40, hi=700)
    pulses = (0.5 + 0.5 * np.sin(2 * np.pi * rate * tt)) ** 3
    breath = 0.55 + 0.45 * np.sin(2 * np.pi * tt / 1.7 - 1.2)  # inhale / exhale
    tone = np.sin(2 * np.pi * rate * 2 * tt) * 0.3
    s = (base * 0.8 + tone) * pulses * breath
    edge = np.minimum(1, tt / 0.3) * np.minimum(1, (sec - tt) / 0.5).clip(0, 1)
    return s * edge


def stereo(left, right=None):
    right = left if right is None else right
    return np.stack([left, right], axis=1)


def master(x, peak=0.8):
    x = x - np.mean(x, axis=0)
    x = np.tanh(x / max(1e-9, np.max(np.abs(x))) * 0.75)
    return x / np.max(np.abs(x)) * peak


def write_mp3(path, x, br="160k", loop=False):
    if x.ndim == 1:
        x = stereo(x)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "wav", "-i", "pipe:0", "-codec:a", "libmp3lame",
                    "-b:a", br, path], input=buf.getvalue(), check=True)


def wav_bytes(x):
    if x.ndim == 1:
        x = stereo(x)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def fade(x, fin=0.02, fout=1.5):
    n = len(x)
    e = np.ones(n)
    a, b = int(fin * SR), int(fout * SR)
    e[:a] = np.linspace(0, 1, a)
    e[n - b:] = np.linspace(1, 0, b)
    return x * (e[:, None] if x.ndim == 2 else e)


# ------------------------------------------------------------------ tracks
def low_ceiling(sec=32.0):
    bpm = 76
    beat = 60 / bpm
    n = int(sec * SR)
    drums = np.zeros(n); bassl = np.zeros(n); pads = np.zeros(n)
    bars = int(sec / (beat * 4)) + 1
    prog = [[50, 57, 62, 65], [46, 53, 58, 62], [48, 55, 60, 63], [45, 52, 57, 61]]
    roots = [38, 34, 36, 33]
    for b in range(bars):
        t0 = b * beat * 4
        place(drums, kick(0.95), t0, 1.0)
        place(drums, kick(0.95), t0 + beat * 2.5, 0.7)
        place(drums, snare(0.22), t0 + beat * 2, 0.8)
        for k in range(8):
            place(drums, hat(0.03), t0 + k * beat / 2 + (0.012 if k % 2 else 0), 0.25 + 0.1 * (k % 2))
        place(pads, pad(prog[b % 4], beat * 4 + 1.2, bright=1300), t0, 0.9)
        place(bassl, bass(roots[b % 4], beat * 1.5), t0, 0.8)
        place(bassl, bass(roots[b % 4], beat * 1.2, glide_from=roots[b % 4] + 5), t0 + beat * 2.5, 0.6)
    drums = reverb(drums, 1.1, 0.45, damp=3000)
    mix = stereo(drums * 0.9 + bassl * 0.8 + pads * 0.55 * 0.9, drums * 0.9 + bassl * 0.8 + pads * 0.55 * 1.1)
    mix = np.stack([tape(mix[:, 0], seed=1), tape(mix[:, 1], seed=2)], axis=1)
    return fade(master(mix))


def barrys_4am(sec=32.0):
    bpm = 84
    beat = 60 / bpm
    n = int(sec * SR)
    keys = np.zeros(n); drums = np.zeros(n); sub = np.zeros(n)
    chords = [[53, 56, 60, 63, 67], [49, 53, 56, 60, 63], [51, 55, 58, 62, 65], [48, 51, 55, 58, 62]]
    roots = [41, 37, 39, 36]
    bars = int(sec / (beat * 4)) + 1
    for b in range(bars):
        t0 = b * beat * 4
        for i, m in enumerate(chords[b % 4]):
            place(keys, epiano(m, beat * 4, 0.9), t0 + i * 0.018)
        for i, m in enumerate(chords[b % 4][2:]):
            place(keys, epiano(m + 12, beat * 1.5, 0.35), t0 + beat * 2.5 + i * 0.03)
        place(drums, kick(1.05, 0.3), t0, 0.75)
        place(drums, kick(1.05, 0.3), t0 + beat * 1.75, 0.45)
        place(drums, rim(), t0 + beat, 0.4)
        place(drums, rim(), t0 + beat * 3, 0.4)
        for k in range(8):
            place(drums, hat(0.025), t0 + k * beat / 2 + (0.02 if k % 2 else 0), 0.16)
        place(sub, bass(roots[b % 4], beat * 3.5), t0, 0.6)
    keys = reverb(keys, 2.2, 0.35, seed=4, damp=5000)
    purr = purr_noise(sec, 25, seed=11) * 0.12
    left = keys * 0.9 + drums * 0.7 + sub * 0.7 + purr
    right = keys * 1.0 + drums * 0.7 + sub * 0.7
    mix = np.stack([tape(left, seed=5), tape(right, seed=6)], axis=1)
    return fade(master(mix))


def cinder(sec=32.0):
    bpm = 140
    beat = 60 / bpm
    n = int(sec * SR)
    drums = np.zeros(n); b8 = np.zeros(n); plk = np.zeros(n)
    bars = int(sec / (beat * 4)) + 1
    roots = [37, 37, 40, 35]
    for b in range(bars):
        t0 = b * beat * 4
        place(drums, kick(0.9, 0.5), t0, 1.0)
        place(drums, kick(0.9, 0.5), t0 + beat * 2.75, 0.8)
        place(drums, snare(0.16, 200), t0 + beat * 2, 0.85)
        for k in range(16):
            roll = (b % 2 == 1 and k >= 12)
            place(drums, hat(0.02), t0 + k * beat / 4, 0.22 if k % 2 else 0.32)
            if roll:
                place(drums, hat(0.015), t0 + k * beat / 4 + beat / 8, 0.18)
        r = roots[b % 4]
        place(b8, bass(r - 12 + 12, beat * 2.5), t0, 0.9)
        place(b8, bass(r - 12 + 12, beat * 1.2, glide_from=r + 7), t0 + beat * 2.75, 0.8)
        for k, m in enumerate([r + 24, r + 31, r + 27, r + 34]):
            place(plk, pluck(m), t0 + k * beat, 0.8)
    # tape echo on plucks
    d = int(beat * 0.75 * SR)
    echo = plk.copy()
    for k in range(1, 5):
        e = np.zeros(n); e[d * k:] = plk[: n - d * k] * (0.45 ** k)
        echo += fft_filter(e, hi=3000 - k * 400)
    plk = reverb(echo, 1.6, 0.3, seed=8)
    mix = stereo(drums * 0.85 + b8 * 0.9 + plk * 0.5 * 1.2, drums * 0.85 + b8 * 0.9 + plk * 0.5 * 0.8)
    mix = np.stack([tape(mix[:, 0], sat=2.0, seed=7), tape(mix[:, 1], sat=2.0, seed=8)], axis=1)
    return fade(master(mix))


def preview_drums(sec=16.0):
    n = int(sec * SR)
    x = np.zeros(n)
    beat = 60 / 92
    hits = [kick(1.0), kick(0.85, 0.6), snare(0.2), snare(0.12, 220), rim(), hat(0.03), hat(open_=True)]
    for i, h in enumerate(hits):  # audition each one-shot
        place(x, h, i * 0.42, 0.9)
    t1 = len(hits) * 0.42 + 0.3
    for b in range(4):
        t0 = t1 + b * beat * 4
        place(x, kick(), t0); place(x, kick(), t0 + beat * 2.5, 0.75)
        place(x, snare(), t0 + beat, 0.8); place(x, snare(), t0 + beat * 3, 0.8)
        for k in range(8):
            place(x, hat(0.03), t0 + k * beat / 2, 0.3)
        place(x, hat(open_=True), t0 + beat * 3.5, 0.3)
    x = reverb(x, 0.9, 0.3, damp=3500)
    return fade(master(stereo(x)), fout=0.8)


def preview_loops(sec=16.0):
    bpm = 90
    beat = 60 / bpm
    n = int(sec * SR)
    k = np.zeros(n); bs = np.zeros(n)
    chords = [[57, 60, 64, 67], [53, 57, 60, 64]]
    for b in range(int(sec / (beat * 4)) + 1):
        t0 = b * beat * 4
        for i, m in enumerate(chords[b % 2]):
            place(k, epiano(m, beat * 2, 0.8), t0 + i * 0.02)
            place(k, epiano(m, beat * 2, 0.6), t0 + beat * 2 + 0.04 + i * 0.02)
        place(bs, bass(45 if b % 2 == 0 else 41, beat * 3), t0, 0.7)
    mix = reverb(k, 1.8, 0.3) + bs * 0.8
    return fade(master(stereo(tape(mix, seed=12), tape(mix, seed=13))), fout=0.8)


def preview_presets(sec=16.0):
    n = int(sec * SR)
    x = np.zeros(n)
    place(x, pad([50, 57, 60, 65], 5.5, bright=900), 0.0, 1.0)
    place(x, pad([46, 53, 58, 62], 5.5, bright=2400, detune=0.2), 5.0, 1.0)
    for k, m in enumerate([74, 72, 69, 67, 65, 69, 72, 77]):
        place(x, pluck(m, 0.8), 10 + k * 0.5, 0.9)
    place(x, bass(38, 4), 10, 0.5)
    x = reverb(x, 2.5, 0.35, seed=21)
    return fade(master(stereo(x * 1.05, x * 0.95)), fin=0.3, fout=1.2)


# ------------------------------------------------------------------ sfx
def room_tone(sec=24.0):
    n = int(sec * SR)
    tt = np.arange(n) / SR
    brown = np.cumsum(rng.standard_normal(n)); brown -= np.convolve(brown, np.ones(4001) / 4001, mode="same")
    brown /= np.max(np.abs(brown))
    air = fft_filter(rng.standard_normal(n), lo=120, hi=900) * (0.7 + 0.3 * np.sin(2 * np.pi * tt / 7.3))
    hum = 0.25 * np.sin(2 * np.pi * 60 * tt) + 0.12 * np.sin(2 * np.pi * 120 * tt) + 0.05 * np.sin(2 * np.pi * 180 * tt)
    x = brown * 0.6 + air * 0.25 + hum * 0.18
    # seamless loop: crossfade tail into head
    cf = int(2.0 * SR)
    w = np.linspace(0, 1, cf)
    x[:cf] = x[:cf] * w + x[-cf:] * (1 - w)
    x = x[:-cf]
    return master(stereo(x, np.roll(x, 3000)), 0.6)


def lamp_click():
    n = int(0.35 * SR)
    tt = np.arange(n) / SR
    c1 = fft_filter(rng.standard_normal(n), lo=1500, hi=9000) * np.exp(-tt / 0.004)
    c2 = np.zeros(n)
    c2[int(0.028 * SR):] = c1[: n - int(0.028 * SR)] * 0.5
    thunk = np.sin(2 * np.pi * 140 * tt) * np.exp(-tt / 0.03) * 0.4
    return master(stereo(c1 + c2 + thunk), 0.7)


def startup():
    n = int(2.2 * SR)
    x = np.zeros(n)
    for i, m in enumerate([60, 67, 71, 74, 79]):
        place(x, epiano(m, 2.0, 0.8), i * 0.045)
    place(x, pad([48, 55, 64], 2.2, bright=1500), 0, 0.5)
    x = reverb(x, 1.6, 0.35)
    return fade(master(stereo(x), 0.6), fin=0.005, fout=0.6)


def purr(seed, sec):
    x = purr_noise(sec, 24 + seed, seed)
    x = reverb(x, 0.5, 0.15)
    return master(stereo(x, x * 0.85), 0.7)


def ui_tick():
    n = int(0.06 * SR)
    tt = np.arange(n) / SR
    return master(stereo(np.sin(2 * np.pi * 1900 * tt) * np.exp(-tt / 0.008)), 0.35)


if __name__ == "__main__":
    jobs = [
        (AUD, "low-ceiling", low_ceiling), (AUD, "barrys-4am", barrys_4am), (AUD, "cinder", cinder),
        (AUD, "preview-drums", preview_drums), (AUD, "preview-loops", preview_loops), (AUD, "preview-presets", preview_presets),
        (SFX, "room-tone", room_tone), (SFX, "lamp-click", lamp_click), (SFX, "startup", startup),
        (SFX, "purr-1", lambda: purr(1, 3.6)), (SFX, "purr-2", lambda: purr(2, 5.0)), (SFX, "tick", ui_tick),
    ]
    for d, name, fn in jobs:
        x = fn()
        write_mp3(os.path.join(d, f"{name}.mp3"), x, "128k" if d == SFX else "160k")
        print(name, f"{len(x) / SR:.1f}s")
    # stand-in paid bundles
    bundles = {
        "purplhrtz-basement-drums-vol-1.zip": {"kick_room_A1.wav": kick(), "snare_block.wav": snare(),
                                              "hat_duct.wav": hat(0.04), "rim_case.wav": rim()},
        "purplhrtz-after-midnight-loops.zip": {"keys_90bpm_Am.wav": preview_loops(8.0)},
        "purplhrtz-bruised-plum-presets.zip": {"bruised_pad_demo.wav": preview_presets(6.0)},
    }
    readme = ("purplhrtz — demo bundle\n\nThis is a stand-in download generated for the demo store.\n"
              "Replace the zip in /private-downloads with the real release.\n\nLicense: royalty-free for use in your releases;"
              " do not resell the files themselves.\n")
    for zname, files in bundles.items():
        with zipfile.ZipFile(os.path.join(DL, zname), "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("README.txt", readme)
            for fname, sig in files.items():
                z.writestr(fname, wav_bytes(master(sig if sig.ndim == 2 else stereo(sig), 0.9)))
        print(zname)
