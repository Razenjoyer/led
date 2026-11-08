"""Проверка детектора бита на искусственном ритме 120 BPM (бочка + шум)."""
import numpy as np

import led_music as m

rate, seconds, bpm = 48000, 8, 120
t = np.arange(rate * seconds) / rate
signal = 0.02 * np.random.randn(t.size)  # фоновый шум (хай-хэты)
for beat_time in np.arange(0, seconds, 60 / bpm):
    i = int(beat_time * rate)
    n = int(0.15 * rate)
    env = np.exp(-np.arange(n) / (0.04 * rate))
    signal[i:i + n] += 0.6 * env * np.sin(2 * np.pi * 60 * np.arange(n) / rate)

a = m.Analyzer(rate, 1.4)
real_time = m.time.monotonic
fake_now = [0.0]
m.time.monotonic = lambda: fake_now[0]
for k in range(0, t.size - m.BLOCK, m.BLOCK):
    fake_now[0] = k / rate
    a.feed(signal[k:k + m.BLOCK].astype(np.float32))
m.time.monotonic = real_time
expected = int(seconds * bpm / 60) - 2  # первая секунда уходит на разгон
print(f"найдено битов: {a.beats}, ожидалось примерно {expected}")
