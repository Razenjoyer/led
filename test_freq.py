"""Проверка режима «Частоты» на искусственных звуках: какой цвет получается."""
import colorsys

import numpy as np

import led_music as m

RATE = 48000
fake_now = [0.0]
m.time.monotonic = lambda: fake_now[0]


def tone(freq, sec, amp=0.3):
    t = np.arange(int(RATE * sec)) / RATE
    return amp * np.sin(2 * np.pi * freq * t)


def noise_band(lo, hi, sec, amp=0.3):
    x = np.random.randn(int(RATE * sec))
    f = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1 / RATE)
    f[(freqs < lo) | (freqs > hi)] = 0
    y = np.fft.irfft(f, x.size)
    return amp * y / np.abs(y).max()


def name(rgb):
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return f"оттенок {h * 360:5.0f}°  насыщ. {s:.2f}  яркость {v:.2f}"


state = m.State(mode="freq")
an = m.Analyzer(RATE, 1.4)
fx = m.Effects(state)


def play(signal, label):
    hues = []
    flashes = sparks = 0
    for k in range(0, signal.size - m.BLOCK, m.BLOCK):
        fake_now[0] += m.BLOCK / RATE
        an.feed(signal[k:k + m.BLOCK].astype(np.float32))
        rgb = fx.frame(*an.snapshot(), m.BLOCK / RATE)
        h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
        hues.append(h * 360)
        flashes += fx.flash == 1.0
        sparks += fx.sparkle == 1.0
    print(f"{label:28s} → в конце: {name(rgb)}   вспышек бочки: {flashes}, искр: {sparks}")


play(tone(60, 4) + noise_band(40, 120, 4, 0.1), "басы (60 Гц)")
play(noise_band(400, 1500, 4), "середина (вокал, 400–1500 Гц)")
play(noise_band(4000, 9000, 4, 0.2), "верха (4–9 кГц)")

# ритм: бочка на каждую долю, хай-хэт между ними, 120 BPM
sec = 6
mix = noise_band(300, 1500, sec, 0.05)
for t0 in np.arange(0, sec, 0.5):
    i, n = int(t0 * RATE), int(0.15 * RATE)
    mix[i:i + n] += 0.6 * np.exp(-np.arange(n) / (0.04 * RATE)) * np.sin(2 * np.pi * 60 * np.arange(n) / RATE)
    j, h = int((t0 + 0.25) * RATE), int(0.05 * RATE)
    if j + h < mix.size:
        mix[j:j + h] += noise_band(6000, 12000, 0.05, 0.25)[:h] * np.exp(-np.arange(h) / (0.01 * RATE))
play(mix, "ритм: бочка + хай-хэт (6 с)")
print("ожидалось в ритме: ~11 вспышек бочки и ~11 искр")
