"""Проверка: в палитре «Огонь» ни в одном режиме не появляется синий."""
import numpy as np

import led_music as m

rate = 48000
fake_now = [0.0]
m.time.monotonic = lambda: fake_now[0]
rng = np.random.default_rng(2)
sec = 6
signal = 0.05 * rng.standard_normal(rate * sec)
for t0 in np.arange(0, sec, 0.5):  # бочка + хай-хэт, как в настоящем треке
    i, n = int(t0 * rate), int(0.15 * rate)
    signal[i:i + n] += 0.6 * np.exp(-np.arange(n) / (0.04 * rate)) * np.sin(2 * np.pi * 60 * np.arange(n) / rate)
    j, h = int((t0 + 0.25) * rate), int(0.05 * rate)
    if j + h < signal.size:
        signal[j:j + h] += 0.3 * rng.standard_normal(h) * np.exp(-np.arange(h) / (0.01 * rate))

for mode in ["freq", "beat", "pulse"]:
    state = m.State(mode=mode)
    state.palette = "Огонь"
    an, fx = m.Analyzer(rate, 1.4), m.Effects(state)
    max_blue, sparks = 0, 0
    for k in range(0, signal.size - m.BLOCK, m.BLOCK):
        fake_now[0] += m.BLOCK / rate
        an.feed(signal[k:k + m.BLOCK].astype(np.float32))
        r, g, b = fx.frame(*an.snapshot(), m.BLOCK / rate)
        max_blue = max(max_blue, b)
        sparks += fx.sparkle == 1.0
    print(f"{mode:6s}: максимум синего = {max_blue} (из 255), искр: {sparks}")
    assert max_blue == 0, mode
print("в «Огне» синего нет")
