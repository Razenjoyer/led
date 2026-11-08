"""Проверка новых функций: дропы и стробоскоп, плавный режим, будильник, таймер сна,
палитра из обложки, цвет экрана, сохранение настроек."""
import datetime as dt
import io
import tempfile
import time as real_time_mod
from pathlib import Path

import numpy as np
from PIL import Image

import led_music as m
import engine
import sources

RATE = 48000
fake = [0.0]
real_monotonic = m.time.monotonic
m.time.monotonic = lambda: fake[0]


def feed(an, fx, signal):
    out = []
    for k in range(0, signal.size - m.BLOCK, m.BLOCK):
        fake[0] += m.BLOCK / RATE
        an.feed(signal[k:k + m.BLOCK].astype(np.float32))
        out.append(fx.frame(*an.snapshot(), m.BLOCK / RATE))
    return out


rng = np.random.default_rng(3)

# 1. Дроп: 4 с тихо, потом громко → стробоскоп (чередование ярко/темно)
state = m.State(mode="freq")
state.strobe = True
an, fx = m.Analyzer(RATE, 1.4), m.Effects(state)
quiet = 0.01 * rng.standard_normal(RATE * 4)
loud = 0.3 * rng.standard_normal(RATE * 2)
feed(an, fx, quiet)
frames = feed(an, fx, loud)
blacks = sum(1 for c in frames[:60] if c == (0, 0, 0))
print(f"дропов: {an.drops} (ожидался 1), тёмных кадров стробоскопа: {blacks}")
assert an.drops == 1 and blacks > 5

# без галочки стробоскопа — вспышек в чёрное нет
state2 = m.State(mode="freq")
an2, fx2 = m.Analyzer(RATE, 1.4), m.Effects(state2)
feed(an2, fx2, quiet)
assert not any(c == (0, 0, 0) for c in feed(an2, fx2, loud)[:60])
print("стробоскоп выключен → вспышек нет: ок")

# 2. Плавный режим: соседние кадры почти не отличаются (нет резких вспышек)
state3 = m.State(mode="calm")
an3, fx3 = m.Analyzer(RATE, 1.4), m.Effects(state3)
kicks = 0.05 * rng.standard_normal(RATE * 4)
for t0 in np.arange(0, 4, 0.5):
    i, n = int(t0 * RATE), int(0.15 * RATE)
    kicks[i:i + n] += 0.6 * np.sin(2 * np.pi * 60 * np.arange(n) / RATE)
fr = feed(an3, fx3, kicks)
jump = max(max(abs(a - b) for a, b in zip(x, y)) for x, y in zip(fr[50:], fr[51:]))
print(f"плавный: самый резкий скачок между кадрами = {jump} (из 255)")
assert jump < 20

# 3. Будильник-рассвет
s = m.State()
s.alarm_enabled, s.alarm_time, s.alarm_minutes = True, "07:30", 30
day = dt.date(2026, 11, 9)
at = lambda h, mi: dt.datetime.combine(day, dt.time(h, mi))
assert engine.alarm_phase(s, at(6, 50)) is None
p_start, p_mid, p_end = (engine.alarm_phase(s, at(7, x)) for x in (0, 15, 45))
print(f"рассвет: 7:00 → {p_start:.2f}, 7:15 → {p_mid:.2f}, 7:45 → {p_end:.2f}; цвета:",
      engine.sunrise_color(0), engine.sunrise_color(0.5), engine.sunrise_color(1))
assert p_start == 0 and abs(p_mid - 0.5) < 1e-6 and p_end == 1.0
assert engine.alarm_phase(s, at(8, 10)) is None  # через 30 мин после будильника — всё
s.alarm_phase_now = engine.alarm_phase(s, at(7, 20))
s.touch()  # нажали что-то в окне — будильник на сегодня выключен
assert engine.alarm_phase(s, at(7, 25)) is None
# будильник сразу после полуночи: рассвет начинается накануне
s2 = m.State()
s2.alarm_enabled, s2.alarm_time, s2.alarm_minutes = True, "00:10", 30
assert engine.alarm_phase(s2, at(23, 55)) is not None
print("будильник: ок (окно, выключение касанием, переход через полночь)")

# 4. Таймер сна
s = m.State()
s.start_sleep(10)
t0 = real_time_mod.time()
f_half = engine.sleep_factor(s, t0 + 300)
f_end = engine.sleep_factor(s, t0 + 601)
print(f"таймер сна: через 5 мин яркость ×{f_half:.2f}, в конце ×{f_end}, лента включена: {s.power}")
assert abs(f_half - 0.5) < 0.01 and f_end == 0 and s.power is False

# 5. Палитра из обложки: картинка из красного и синего → оба цвета в палитре
img = Image.new("RGB", (100, 100), (200, 20, 20))
img.paste((20, 40, 220), (50, 0, 100, 100))
buf = io.BytesIO()
img.save(buf, "PNG")
pal = sources.palette_from_image(buf.getvalue())
print("палитра обложки:", pal)
assert pal and len(pal) >= 2
assert any(c[0] > 0.9 and c[2] < 0.3 for c in pal) and any(c[2] > 0.9 and c[0] < 0.3 for c in pal)
gray = Image.new("RGB", (50, 50), (128, 128, 128))
buf = io.BytesIO()
gray.save(buf, "PNG")
assert sources.palette_from_image(buf.getvalue()) is None
print("серая обложка → обычная палитра: ок")

# 6. Цвет экрана: зелёный экран с белым окном → зелёный
frame = np.zeros((1200, 1920, 4), dtype=np.uint8)
frame[..., 1] = 180  # зелёный (BGRA)
frame[300:900, 400:1500, :3] = 240  # белое окно
r, g, b = sources.screen_color(frame)
print(f"цвет экрана: ({r:.2f}, {g:.2f}, {b:.2f})")
assert g > 0.6 and r < 0.3 and b < 0.3

# 7. Сохранение настроек
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "s.json"
    s = m.State(mode="calm")
    s.palette, s.order, s.alarm_time = "Огонь", "GRB", "06:45"
    s.save(p)
    s2 = m.State()
    s2.load(p)
    assert (s2.mode, s2.palette, s2.order, s2.alarm_time) == ("calm", "Огонь", "GRB", "06:45")
print("сохранение настроек: ок")

m.time.monotonic = real_monotonic
print("ВСЕ ПРОВЕРКИ ПРОШЛИ")
