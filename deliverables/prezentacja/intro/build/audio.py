import wave
from pathlib import Path

import numpy as np

SR = 48000
DUR = 8.6
OUT = Path(__file__).resolve().parent.parent / "intro.wav"
rng = np.random.default_rng(2026)
n = int(SR * DUR)
mix = np.zeros(n)
t_all = np.arange(n) / SR


def place(sig, at, gain=1.0):
    i = int(at * SR)
    end = min(n, i + len(sig))
    mix[i:end] += sig[: end - i] * gain


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def thump(strength=1.0, dur=0.45):
    t = np.arange(int(SR * dur)) / SR
    freq = 38 + 34 * np.exp(-t / 0.05)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    env = (1 - np.exp(-t / 0.004)) * np.exp(-t / 0.09)
    body = np.sin(phase) + 0.25 * np.sin(2 * phase)
    click = lowpass(rng.standard_normal(len(t)), 900) * np.exp(-t / 0.012) * 0.9
    return np.tanh(1.6 * (body * env + click)) * strength


def blip(freq=1046, dur=0.11):
    t = np.arange(int(SR * dur)) / SR
    env = np.minimum(1, t / 0.004) * np.exp(-t / 0.04)
    return np.sin(2 * np.pi * freq * t) * env


def charge(start, end):
    t = np.arange(int(SR * (end - start))) / SR
    p = t / t[-1]
    freq = 420 * (2900 / 420) ** (p ** 1.3)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    env = p ** 1.6 * (1 - np.exp(-(1 - p + 1e-4) / 0.01)) * (1 + 0.12 * np.sin(2 * np.pi * 11 * t))
    return (np.sin(phase) + 0.18 * np.sin(2 * phase) + 0.06 * np.sin(3 * phase)) * env


def zap(dur=0.35):
    t = np.arange(int(SR * dur)) / SR
    noise = rng.standard_normal(len(t))
    crackle = noise - lowpass(noise, 2500)
    return crackle * np.exp(-t / 0.035) * 0.5 + thump(0.8, dur) * 0.9


def whoosh(start, end):
    m = int(SR * (end - start))
    p = np.linspace(0, 1, m)
    env = np.sin(np.pi * p) ** 2
    noise = rng.standard_normal(m)
    return lowpass(noise, 700) * env * 3.0


place(blip(), 0.12, 0.10)
place(blip(1046, 0.09), 0.40, 0.05)
place(charge(0.55, 2.13), 0.55, 0.07)
place(zap(), 2.13, 0.55)
for b in (2.45, 3.35):
    place(thump(1.0), b - 0.012)
    place(thump(0.62), b + 0.22 - 0.012)
place(whoosh(3.95, 5.0), 3.95, 0.16)
place(blip(1568, 0.14), 5.5, 0.07)

pad_env = np.clip((t_all - 0.4) / 1.6, 0, 1) * np.clip((8.3 - t_all) / 1.4, 0, 1)
pad = (np.sin(2 * np.pi * 55 * t_all) + 0.5 * np.sin(2 * np.pi * 82.4 * t_all) + 0.25 * np.sin(2 * np.pi * 110 * t_all + 0.6 * np.sin(2 * np.pi * 0.3 * t_all)))
mix += pad * pad_env * 0.035

ir_t = np.arange(int(SR * 0.9)) / SR
ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.22)
ir /= np.sqrt(np.sum(ir ** 2))
size = 1 << int(np.ceil(np.log2(n + len(ir))))
wet = np.fft.irfft(np.fft.rfft(mix, size) * np.fft.rfft(ir, size), size)[:n]
out = mix + 0.18 * wet

fade = np.clip((DUR - t_all) / 0.3, 0, 1)
out *= fade
out /= np.max(np.abs(out)) / 0.89

stereo = np.stack([out, out], axis=1)
with wave.open(str(OUT), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((stereo * 32767).astype(np.int16).tobytes())
print("->", OUT)
