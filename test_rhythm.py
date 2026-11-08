"""Проверка определения темпа (BPM) и припева на искусственной музыке."""
import numpy as np

import led_music as m

RATE = 48000
fake = [0.0]
m.time.monotonic = lambda: fake[0]
rng = np.random.default_rng(5)


def track(bpm, seconds, amp=1.0, hats=True):
    sig = 0.03 * rng.standard_normal(RATE * seconds)
    period = 60 / bpm
    for t0 in np.arange(0, seconds, period):
        i, n = int(t0 * RATE), int(0.15 * RATE)
        if i + n < sig.size:
            sig[i:i + n] += 0.6 * np.exp(-np.arange(n) / (0.04 * RATE)) * np.sin(2 * np.pi * 55 * np.arange(n) / RATE)
        j, h = int((t0 + period / 2) * RATE), int(0.04 * RATE)
        if hats and j + h < sig.size:
            sig[j:j + h] += 0.2 * rng.standard_normal(h) * np.exp(-np.arange(h) / (0.01 * RATE))
    return amp * sig


def feed(an, sig):
    for k in range(0, sig.size - m.BLOCK, m.BLOCK):
        fake[0] += m.BLOCK / RATE
        an.feed(sig[k:k + m.BLOCK].astype(np.float32))


ok = True
for bpm in (90, 100, 120, 128, 140, 150, 174):
    an = m.Analyzer(RATE, 1.4)
    feed(an, track(bpm, 14))
    got = an.snapshot()[0]["bpm"]
    good = abs(got - bpm) / bpm < 0.04
    ok &= good
    print(f"темп {bpm:3d} BPM → найдено {got:6.1f}  {'ок' if good else 'ОШИБКА'}")

# припев: 20 с куплет потише, 12 с припев громче, 15 с снова куплет
an = m.Analyzer(RATE, 1.4)
timeline = []
for part, amp, sec in (("куплет", 0.35, 20), ("припев", 1.0, 12), ("куплет", 0.35, 15)):
    sig = track(120, sec, amp)
    for k in range(0, sig.size - m.BLOCK, m.BLOCK):
        fake[0] += m.BLOCK / RATE
        an.feed(sig[k:k + m.BLOCK].astype(np.float32))
        timeline.append((part, an.snapshot()[0]["chorus"]))
per_sec = RATE / m.BLOCK


def share(part_idx, start_s, end_s):
    seg = timeline[int(start_s * per_sec):int(end_s * per_sec)]
    return sum(c for _, c in seg) / max(1, len(seg))


verse1, chorus, verse2 = share(0, 8, 20), share(1, 23, 32), share(2, 40, 47)
print(f"припев: в куплете {verse1:.0%} времени, в припеве {chorus:.0%}, во втором куплете {verse2:.0%}")
ok &= verse1 < 0.05 and chorus > 0.6 and verse2 < 0.2
print("ВСЕ ПРОВЕРКИ ПРОШЛИ" if ok else "ЕСТЬ ОШИБКИ")
