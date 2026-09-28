"""Effets sonores générés par le code (aucun droit d'auteur) : whoosh, pop, tick."""
import wave

import numpy as np

SR = 44100


def _env(n, attack, release):
    a = max(int(attack * SR), 1)
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    e[a:] = np.exp(-np.linspace(0, 1, n - a) * release)
    return e


def whoosh(dur=0.45, reverse=False, seed=0):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    # passe-bas dont la fréquence de coupure monte puis redescend
    cut = 250 + 4200 * np.sin(np.linspace(0, np.pi, n)) ** 2
    alpha = 1 - np.exp(-2 * np.pi * cut / SR)
    out = np.empty(n)
    y = 0.0
    for i in range(n):
        y += alpha[i] * (noise[i] - y)
        out[i] = y
    env = np.sin(np.linspace(0, np.pi, n)) ** 1.5
    out = out * env
    out /= np.abs(out).max() + 1e-9
    return out[::-1] if reverse else out


def pop(dur=0.12, f0=900, f1=420):
    n = int(dur * SR)
    freq = np.linspace(f0, f1, n)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    s = np.sin(phase) * _env(n, 0.002, 7)
    return s / (np.abs(s).max() + 1e-9)


def tick(dur=0.05, f=1800):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) * _env(n, 0.001, 12)
    return s / (np.abs(s).max() + 1e-9)


def compose(total, events, path):
    """events : liste de (temps_en_s, nom, gain). Écrit un WAV mono 16 bits."""
    track = np.zeros(int((total + 1) * SR))
    sounds = {"whoosh": whoosh(), "whoosh_rev": whoosh(reverse=True, seed=1), "pop": pop(), "tick": tick()}
    for t, name, gain in events:
        s = sounds[name] * gain
        i = int(max(t, 0) * SR)
        j = min(i + len(s), len(track))
        track[i:j] += s[: j - i]
    peak = np.abs(track).max()
    if peak > 0.95:
        track *= 0.95 / peak
    data = (track * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path
