import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
RATE = 44100
rng = np.random.default_rng(11)


def timeline(seconds):
    return np.arange(int(seconds * RATE)) / RATE


def curve(t, points):
    xs, ys = zip(*points)
    return np.interp(t / t[-1], xs, ys)


def envelope(t, attack, release, shape=1.0):
    env = np.minimum(1, t / attack) * np.minimum(1, (t[-1] - t) / release)
    return np.clip(env, 0, 1) ** shape


def bandpass_noise(n, low, high):
    spectrum = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    spectrum *= np.exp(-0.5 * ((freqs - (low + high) / 2) / ((high - low) / 2)) ** 2)
    out = np.fft.irfft(spectrum, n)
    return out / (np.abs(out).max() + 1e-9)


def voice(t, f0, formants, tilt=0.9, jitter=0.0, breath=0.0, subharmonic=0.0):
    f0 = f0 * (1 + jitter * np.convolve(rng.standard_normal(len(t)), np.ones(200) / 200, "same") * 8)
    phase = 2 * np.pi * np.cumsum(f0) / RATE
    out = np.zeros(len(t))
    for k in range(1, int(9000 / f0.min())):
        freq = k * f0
        gain = sum(g * np.exp(-0.5 * ((freq - fc) / bw) ** 2) for fc, bw, g in formants)
        out += gain / k ** tilt * np.sin(k * phase + rng.uniform(0, 2 * np.pi)) * (freq < RATE / 2)
    if subharmonic:
        out += subharmonic * np.sin(phase / 2) * np.abs(out).max()
    if breath:
        centre = np.mean([np.mean(fc) for fc, _, _ in formants[:2]])
        out += breath * bandpass_noise(len(t), centre * 0.5, centre * 2.2) * np.abs(out).max()
    return out


def room(signal, mix=0.12, length=0.07):
    ir_t = timeline(length)
    ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / (length / 5))
    n = len(signal) + len(ir)
    wet = np.fft.irfft(np.fft.rfft(signal, n) * np.fft.rfft(ir, n), n)
    wet = wet / (np.abs(wet).max() + 1e-9) * np.abs(signal).max()
    dry = np.concatenate([signal, np.zeros(len(ir))])
    return dry * (1 - mix) + wet * mix


def meow(seconds, pitch, vowel_open, rise_end=False):
    t = timeline(seconds)
    shape = [(0, 0.72), (0.3, 1.0), (0.7, 0.86), (1, 1.12 if rise_end else 0.6)]
    f0 = pitch * curve(t, shape) * (1 + 0.015 * np.sin(2 * np.pi * 6 * t))
    f1 = curve(t, [(0, 380), (0.35, 820 * vowel_open), (0.75, 700), (1, 450)])
    f2 = curve(t, [(0, 2300), (0.35, 1700), (0.75, 1150), (1, 850)])
    f3 = curve(t, [(0, 3100), (1, 2800)])
    sound = voice(t, f0, [(f1, 160, 1.0), (f2, 220, 0.75), (f3, 300, 0.35), (4200, 500, 0.12)],
                  tilt=0.75, jitter=0.004, breath=0.06)
    nasal = np.clip(1 - t / 0.09, 0, 1) * 0.55
    return sound * envelope(t, 0.07, 0.16, 1.4) * (1 - nasal)


def bark(seconds, pitch, gruff):
    t = timeline(seconds)
    f0 = pitch * curve(t, [(0, 1.15), (0.25, 1.0), (1, 0.72)])
    f1 = curve(t, [(0, 720), (1, 520)])
    f2 = curve(t, [(0, 1450), (1, 1050)])
    sound = voice(t, f0, [(260, 180, 0.7), (f1, 220, 1.0), (f2, 300, 0.7), (2600, 450, 0.35)],
                  tilt=0.6, jitter=0.02 * gruff, breath=0.25 * gruff, subharmonic=0.12 * gruff)
    burst = bandpass_noise(len(t), 500, 3200) * np.exp(-t / 0.018) * 0.9 * np.abs(sound).max()
    return (sound + burst) * np.exp(-t / (seconds * 0.45)) * envelope(t, 0.006, 0.03)


def bubbles(count, low, high, spread):
    total = timeline(spread + 0.25)
    out = np.zeros(len(total))
    for start in np.sort(rng.uniform(0, spread, count)):
        radius_hz = rng.uniform(low, high)
        t = timeline(0.12)
        tau = 0.012 + 12 / radius_hz
        freq = radius_hz * (1 + 2.2 * t / t[-1])
        blip = np.sin(2 * np.pi * np.cumsum(freq) / RATE) * np.exp(-t / tau) * np.minimum(1, t / 0.002)
        i = int(start * RATE)
        out[i:i + len(t)] += blip * rng.uniform(0.5, 1.0)
    return out


def crunch(seconds, clicks, low, high, thump):
    t = timeline(seconds)
    out = np.zeros(len(t))
    grain = bandpass_noise(len(t), low, high)
    for start in rng.uniform(0, seconds * 0.7, clicks):
        i = int(start * RATE)
        n = int(rng.uniform(0.002, 0.009) * RATE)
        out[i:i + n] += grain[i:i + n] * np.exp(-np.arange(len(out[i:i + n])) / (n / 3)) * rng.uniform(0.3, 1.0)
    jaw = np.sin(2 * np.pi * thump * t) * np.exp(-t / 0.03) * 0.5
    return out + jaw * np.abs(out).max()


def gulp(pitch):
    t = timeline(0.18)
    freq = pitch * (1 + 1.6 * t / t[-1])
    body = np.sin(2 * np.pi * np.cumsum(freq) / RATE) * np.exp(-t / 0.04) * np.minimum(1, t / 0.004)
    return np.concatenate([body, bubbles(2, pitch * 1.8, pitch * 2.6, 0.12) * 0.35])


def sequence(*parts):
    return np.concatenate([p if isinstance(p, np.ndarray) else np.zeros(int(p * RATE)) for p in parts])


def save(path, signal):
    signal = room(signal)
    signal = signal / (np.abs(signal).max() + 1e-9) * 0.7
    fade = np.minimum(1, np.arange(len(signal))[::-1] / (0.01 * RATE))
    pcm = (signal * fade * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm.tobytes())
    print(f"{path.relative_to(ROOT)}  {len(pcm) / RATE:.2f}s")


SOUNDS = {
    "orange_cat": [meow(0.72, 640, 1.0), meow(0.42, 820, 0.8), meow(0.9, 560, 1.1, rise_end=True)],
    "dalmatian": [sequence(bark(0.17, 420, 1.0), 0.13, bark(0.2, 390, 1.0)), bark(0.22, 360, 1.3),
                  sequence(bark(0.12, 600, 0.6), 0.07, bark(0.12, 620, 0.6), 0.07, bark(0.14, 580, 0.6))],
    "goldfish": [bubbles(4, 380, 900, 0.35), bubbles(2, 300, 600, 0.2), bubbles(7, 500, 1300, 0.6)],
}


EAT_SOUNDS = {
    "dalmatian": [crunch(0.16, 28, 900, 6500, 95), crunch(0.14, 22, 800, 6000, 85), crunch(0.18, 34, 1000, 7000, 100)],
    "orange_cat": [crunch(0.09, 9, 2000, 8000, 160), crunch(0.08, 7, 2200, 8500, 170), crunch(0.1, 11, 1800, 7500, 150)],
    "goldfish": [gulp(240), gulp(290), gulp(210)],
}


def main():
    for kind, table in (("sound", SOUNDS), ("eat", EAT_SOUNDS)):
        for folder, variants in table.items():
            for old in (ASSETS / folder).glob(f"{kind}*.wav"):
                old.unlink()
            for i, signal in enumerate(variants, start=1):
                save(ASSETS / folder / f"{kind}{i}.wav", signal)


if __name__ == "__main__":
    main()
