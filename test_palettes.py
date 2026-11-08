"""Проверка палитр: каждый режим с каждой палитрой выдаёт корректные цвета."""
import numpy as np

import led_music as m

rate = 48000
fake_now = [0.0]
m.time.monotonic = lambda: fake_now[0]
rng = np.random.default_rng(1)
signal = 0.05 * rng.standard_normal(rate * 4)
for t0 in np.arange(0, 4, 0.5):
    i, n = int(t0 * rate), int(0.15 * rate)
    signal[i:i + n] += 0.6 * np.exp(-np.arange(n) / (0.04 * rate)) * np.sin(2 * np.pi * 60 * np.arange(n) / rate)

for name in m.PALETTES:
    for mode in ["freq", "beat", "pulse"]:
        state = m.State(mode=mode)
        state.palette = name
        an, fx = m.Analyzer(rate, 1.4), m.Effects(state)
        colors = set()
        for k in range(0, signal.size - m.BLOCK, m.BLOCK):
            fake_now[0] += m.BLOCK / rate
            an.feed(signal[k:k + m.BLOCK].astype(np.float32))
            rgb = fx.frame(*an.snapshot(), m.BLOCK / rate)
            assert len(rgb) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in rgb), rgb
            colors.add(rgb)
        assert len(colors) > 5, (name, mode, len(colors))
    print(f"{name:14s} начало {m.shade(m.palette_rgb(name, 0))}  конец {m.shade(m.palette_rgb(name, 1))}  ок")
print("все палитры и режимы работают")
