"""Ścieżka dźwiękowa części głównej: cichy podkład, dwa uderzenia serca w haku i lektor (jeśli jest)."""

import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

B = Path(__file__).resolve().parent
W = B.parent
SR = 48000
segments = json.loads(sys.argv[1])
total = float(sys.argv[2])
n = int(SR * total)
t = np.arange(n) / SR
rng = np.random.default_rng(7)


def thump(strength, dur=0.45):
    tt = np.arange(int(SR * dur)) / SR
    freq = 38 + 34 * np.exp(-tt / 0.05)
    ph = 2 * np.pi * np.cumsum(freq) / SR
    env = (1 - np.exp(-tt / 0.004)) * np.exp(-tt / 0.09)
    return np.tanh(1.6 * (np.sin(ph) + 0.25 * np.sin(2 * ph)) * env) * strength


def place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i] * gain


pad = (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 82.4 * t) + 0.3 * np.sin(2 * np.pi * 110 * t + 0.6 * np.sin(2 * np.pi * 0.2 * t))
       + 0.12 * np.sin(2 * np.pi * 220 * t + np.sin(2 * np.pi * 0.13 * t)))
env = np.clip(t / 2.0, 0, 1) * np.clip((total - t) / 2.5, 0, 1)
music = pad * env * 0.05

hook = next(s for s in segments if s["id"] == "hak")
for k in range(2):
    beat = hook["vo"] + 0.2 + k * 0.95
    place(music, thump(0.5), beat)
    place(music, thump(0.3), beat + 0.22)

voice = np.zeros(n)
for s in segments:
    mp3 = W / "lektor" / (s["id"] + ".mp3")
    if not mp3.exists():
        continue
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True).stdout
    sig = np.frombuffer(pcm, dtype=np.int16).astype(np.float64) / 32768
    place(voice, sig, s["vo"])

if np.any(voice):
    duck = np.convolve(np.abs(voice) > 0.02, np.ones(int(SR * 0.4)) / (SR * 0.4), mode="same")
    music *= 1 - 0.55 * np.clip(duck * 3, 0, 1)
mix = music + voice
mix /= max(np.max(np.abs(mix)) / 0.9, 1e-9)
with wave.open(str(B / "glowna.wav"), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((np.stack([mix, mix], 1) * 32767).astype(np.int16).tobytes())
print("glowna.wav", round(total, 1), "s", "z lektorem" if np.any(voice) else "bez lektora")
