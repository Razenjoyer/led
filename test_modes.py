"""Проверка новых режимов: «Такт», «Свой», смена палитры на припеве и готовые эффекты."""
import numpy as np

import led_music as m
from effects import AMBIENT_MODES

RATE = 48000
DT = m.BLOCK / RATE
fake = [0.0]
m.time.monotonic = lambda: fake[0]
rng = np.random.default_rng(7)
ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(("ок     " if cond else "ОШИБКА ") + label)


def track(bpm, seconds, amp=1.0):
    sig = 0.03 * rng.standard_normal(RATE * seconds)
    period = 60 / bpm
    for t0 in np.arange(0, seconds, period):
        i, n = int(t0 * RATE), int(0.15 * RATE)
        if i + n < sig.size:
            sig[i:i + n] += 0.6 * np.exp(-np.arange(n) / (0.04 * RATE)) * np.sin(2 * np.pi * 55 * np.arange(n) / RATE)
        j, h = int((t0 + period / 2) * RATE), int(0.04 * RATE)
        if j + h < sig.size:
            sig[j:j + h] += 0.2 * rng.standard_normal(h) * np.exp(-np.arange(h) / (0.01 * RATE))
    return amp * sig


def run(state, sig, on_frame=None):
    an, fx = m.Analyzer(RATE, 1.4), m.Effects(state, seed=1)
    frames = []
    for k in range(0, sig.size - m.BLOCK, m.BLOCK):
        fake[0] += DT
        an.feed(sig[k:k + m.BLOCK].astype(np.float32))
        snap = an.snapshot()
        frames.append(fx.frame(*snap, DT))
        if on_frame:
            on_frame(fx, snap, fake[0])
    return frames


# 1. «Такт»: при 120 BPM смена цвета каждые ~0.5 с
ticks, last_pos = [], [None]


def on_tick(fx, snap, t):
    if last_pos[0] is not None and fx.pos != last_pos[0]:
        ticks.append(t)  # позиция в палитре сдвинулась — это смена цвета
    last_pos[0] = fx.pos


s = m.State(mode="tempo")
run(s, track(120, 16), on_tick)
late = [t for t in ticks if t > ticks[0] + 6]  # после разгона
gaps = np.diff(late)
check(f"«Такт» 120 BPM: {len(late)} смен цвета, средний интервал {gaps.mean():.3f} с (нужно 0.500)",
      abs(gaps.mean() - 0.5) < 0.02 and gaps.std() < 0.05)

# 2. «Свой»: без искр — искр нет; сила вспышки 0 — ярче не становится
s = m.State(mode="custom")
s.custom = {"speed": 50, "flash": 100, "base": 20, "sparkle": False}
sparks = []
bright_hi = max(max(c) for c in run(s, track(120, 6), lambda fx, *_: sparks.append(fx.sparkle)))
check("«Свой» с выключенными искрами: искр нет", max(sparks) == 0)
s.custom = {"speed": 50, "flash": 0, "base": 20, "sparkle": False}
bright_lo = max(max(c) for c in run(s, track(120, 6)))
check(f"«Свой»: вспышка 100 → яркость до {bright_hi}, вспышка 0 → до {bright_lo}", bright_hi > bright_lo + 30)

# 3. Припев: с палитрой «Океан» на припеве цвета синие, в куплете «Огонь» без синего
s = m.State(mode="freq")
s.palette, s.chorus_switch, s.chorus_palette = "Огонь", True, "Океан"
parts = []
sig = np.concatenate([track(120, 20, 0.35), track(120, 12, 1.0)])
frames = run(s, sig, lambda fx, snap, t: parts.append(fx.in_chorus))
verse_blue = max(c[2] for c, ch in zip(frames, parts) if not ch)
chorus_blue = max(c[2] for c, ch in zip(frames, parts) if ch) if any(parts) else 0
check(f"припев найден ({sum(parts)} кадров), синий в куплете {verse_blue}, в припеве {chorus_blue}",
      any(parts) and verse_blue == 0 and chorus_blue > 150)
s.chorus_palette = "auto"
frames = run(s, sig)
check("«авто» на припеве: «Огонь» остаётся без синего", max(c[2] for c in frames) == 0)

# 4. Готовые эффекты
for mode in sorted(AMBIENT_MODES):
    s = m.State(mode=mode)
    fx = m.Effects(s, seed=3)
    level = {"bass": 0, "mid": 0, "high": 0, "centroid": 9, "bpm": 0, "chorus": False}
    frames = []
    for _ in range(25 * 30):  # 30 секунд по 25 кадров
        fake[0] += 0.04
        frames.append(fx.frame(level, 0.0, {"beats": 0, "hats": 0, "drops": 0}, 0.04))
    arr = np.array(frames)
    jump = np.abs(np.diff(arr, axis=0)).max()
    if mode == "police":
        red = any(c[0] > 200 and c[2] < 50 for c in frames)
        blue = any(c[2] > 200 and c[0] < 50 for c in frames)
        check(f"мигалка: красный {red}, синий {blue}, есть паузы", red and blue and (0, 0, 0) in frames)
    elif mode == "storm":
        flashes = sum(1 for c in frames if min(c) > 120)
        check(f"гроза: кадров с молнией {flashes} из {len(frames)}, остальное тёмное",
              0 < flashes < len(frames) * 0.1 and np.median(arr.max(axis=1)) < 60)
    elif mode == "candle":
        check(f"свеча: тёплая (синего максимум {arr[:, 2].max()}), мерцает (разброс яркости {arr[:, 0].std():.0f})",
              arr[:, 2].max() < 20 and arr[:, 0].std() > 8)
    elif mode == "fire":
        check(f"камин: без синего ({arr[:, 2].max()}), живой (разброс {arr[:, 0].std():.0f})",
              arr[:, 2].max() == 0 and arr[:, 0].std() > 15)
    elif mode == "aurora":
        check(f"сияние: плавное (макс. скачок {jump}), есть зелёный и фиолетовый",
              jump < 15 and any(c[1] > 120 and c[0] < 60 for c in frames))

print("ВСЕ ПРОВЕРКИ ПРОШЛИ" if ok else "ЕСТЬ ОШИБКИ")
