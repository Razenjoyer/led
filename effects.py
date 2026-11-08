"""Световые эффекты: из звука, экрана или «сами по себе» получаем цвет ленты."""
import math
import random
import time

from palettes import PALETTES, palette_rgb, pingpong, shade

# (название, подсказка)
MODE_INFO = {
    "manual": ("Ручной цвет", "один выбранный цвет"),
    "freq": ("Частоты", "басы тёплые, верха холодные, бочка вспыхивает"),
    "beat": ("Бит", "новый цвет на каждый удар бочки"),
    "tempo": ("Такт", "цвет меняется строго в темп песни (BPM)"),
    "pulse": ("Пульс", "яркость от басов, цвет переливается"),
    "calm": ("Плавный", "спокойное дыхание без вспышек"),
    "custom": ("Свой", "как «Частоты», но настраивается ползунками"),
    "spectrum": ("Спектр", "басы/середина/верха = R/G/B"),
    "screen": ("Экран", "цвет того, что на мониторе"),
    "candle": ("Свеча", "тёплое живое мерцание"),
    "fire": ("Камин", "языки пламени"),
    "storm": ("Гроза", "тёмная синева и вспышки молний"),
    "police": ("Мигалка", "красно-синие вспышки"),
    "aurora": ("Сияние", "северное сияние: зелёный, бирюзовый, фиолетовый"),
}
MODES = list(MODE_INFO)
MODE_LABELS = {k: f"{n} — {h}" for k, (n, h) in MODE_INFO.items()}
MUSIC_MODES = ["freq", "beat", "tempo", "pulse", "calm", "custom", "spectrum"]
OTHER_MODES = ["manual", "screen", "candle", "fire", "storm", "police", "aurora"]
PALETTE_MODES = {"freq", "beat", "tempo", "pulse", "calm", "custom"}
AMBIENT_MODES = {"candle", "fire", "storm", "police", "aurora"}
STROBE_SECONDS = 1.2
DEFAULT_CUSTOM = {"speed": 50, "flash": 60, "base": 20, "sparkle": True}

AURORA = [(0, 1, 0.45), (0, 0.85, 0.75), (0.1, 0.45, 1), (0.55, 0, 1)]


class Effects:
    def __init__(self, state, seed=None):
        self.state = state
        self.rng = random.Random(seed)
        self.pos = self.rng.random()  # позиция в палитре для «Бита», «Пульса», «Плавного», «Такта» и тишины
        self.flash = 0.0
        self.sparkle = 0.0
        self.seen = {"beats": 0, "hats": 0, "drops": 0}
        self.quiet_since = None
        self.tone = 0.5  # 0 — басы (начало палитры), 1 — верха (конец), сглаженно
        self.lo, self.hi = 8.0, 11.0  # границы «центра тяжести» спектра для этой песни, в октавах
        self.calm_level = 0.3
        self.strobe_until = 0.0
        self.screen_rgb = (0.0, 0.0, 0.0)
        self.in_chorus = False
        self.next_tick = None  # следующий удар в режиме «Такт»
        self.tick_flash = 0.0
        self.noise = {}  # плавный шум для свечи и камина
        self.lightning = []  # вспышки молнии: [(начало, конец), ...]
        self.next_storm = None

    # ---------- палитра (с учётом припева) ----------

    def palette_now(self):
        """(палитра, перевёрнута ли). На припеве — палитра припева; «авто» — та же палитра задом наперёд:
        картинка заметно меняется, но оттенки остаются теми, что вы выбрали."""
        s = self.state
        if not (getattr(s, "chorus_switch", False) and self.in_chorus):
            return s.palette, False
        if s.chorus_palette in PALETTES and s.chorus_palette != s.palette:
            return s.chorus_palette, False
        return s.palette, True

    def color(self, t):
        name, flipped = self.palette_now()
        return palette_rgb(name, 1 - t if flipped else t)

    # ---------- главный кадр ----------

    def frame(self, level, loudness, events, dt):
        mode = self.state.mode
        now = time.monotonic()
        if mode == "manual":
            return self.state.color
        if mode == "screen":
            return self.screen_frame(dt)
        if mode in AMBIENT_MODES:
            return getattr(self, f"{mode}_frame")(now, dt)

        if loudness < 0.0015:
            self.quiet_since = self.quiet_since or now
        else:
            self.quiet_since = None
        if self.quiet_since and now - self.quiet_since > 2:
            # тишина: медленно переливаемся тусклыми цветами палитры
            self.pos += dt * 0.02
            return shade(self.color(pingpong(self.pos)), 0.08)

        new = {k: events[k] != self.seen[k] for k in self.seen}
        self.seen = {k: events[k] for k in self.seen}
        self.flash = max(0.0, self.flash - dt * 4)  # вспышка гаснет за ~0.25 с
        self.sparkle = max(0.0, self.sparkle - dt * 7)  # искра гаснет за ~0.15 с

        chorus = bool(level.get("chorus"))
        if chorus and not self.in_chorus and getattr(self.state, "chorus_switch", False):
            self.flash = 1.0  # начало припева — яркая вспышка новой палитрой
        self.in_chorus = chorus

        # стробоскоп на дропе: ~12 вспышек в секунду цветом верхов палитры
        if new["drops"] and self.state.strobe and mode != "calm":
            self.strobe_until = now + STROBE_SECONDS
        if now < self.strobe_until:
            on = int((self.strobe_until - now) * 12.5) % 2 == 0
            return shade(self.color(1.0), 1.0) if on else (0, 0, 0)

        if mode == "freq":
            return self.freq_frame(level, new["beats"], new["hats"], dt)
        if mode == "custom":
            c = {**DEFAULT_CUSTOM, **(getattr(self.state, "custom", None) or {})}
            return self.freq_frame(level, new["beats"], new["hats"], dt,
                                   smooth=1.5 + 0.18 * c["speed"], flash_k=0.9 * c["flash"] / 100,
                                   base=0.05 + 0.45 * c["base"] / 100, sparkles=bool(c["sparkle"]))
        if mode == "tempo":
            return self.tempo_frame(level, new["beats"], now, dt)
        if mode == "spectrum":
            return tuple(int(255 * v) for v in (level["bass"], level["mid"] * 0.8, level["high"]))
        if mode == "pulse":
            self.pos += dt * 0.05
            return shade(self.color(pingpong(self.pos)), 0.1 + 0.9 * level["bass"] ** 1.5 + 0.5 * self.flash)
        if mode == "calm":
            return self.calm_frame(level, dt)

        # beat: на каждый удар новый цвет из палитры и вспышка
        if new["beats"]:
            self.pos += self.rng.uniform(0.2, 0.45)
            self.flash = 1.0
        base = 0.15 + 0.25 * level["mid"]
        return shade(self.color(pingpong(self.pos)), base + self.flash * 0.85)

    # ---------- музыкальные режимы ----------

    def freq_frame(self, level, new_beat, new_hat, dt, smooth=6.0, flash_k=0.6, base=0.2, sparkles=True):
        """Басы — начало палитры, верха — конец.
        Бочка даёт вспышку цветом басов, хай-хэты и тарелки — искру цветом верхов палитры
        (не белым: белый на таких лентах выглядит голубым и выбивается из тёплых палитр)."""
        c = level["centroid"]
        # границы подстраиваются под песню: расширяются сразу, сужаются медленно
        self.lo = min(c, self.lo + (c - self.lo) * dt * 0.08)
        self.hi = max(c, self.hi + (c - self.hi) * dt * 0.08)
        if self.hi - self.lo < 2.5:  # не меньше 2.5 октав, иначе цвет дёргается от шума
            mid = (self.hi + self.lo) / 2
            self.lo, self.hi = mid - 1.25, mid + 1.25
        relative = (c - self.lo) / (self.hi - self.lo)  # относительно этой песни
        absolute = (c - 7.5) / (12.3 - 7.5)  # фиксированная шкала: 180 Гц … 5 кГц
        target = 0.35 * relative + 0.65 * max(0.0, min(1.0, absolute))
        self.tone += (target - self.tone) * min(1.0, dt * smooth)
        if new_beat:
            self.flash = 1.0
            self.tone *= 0.4  # удар бочки тянет цвет к басовому
        if new_hat and sparkles:
            self.sparkle = 1.0
        spark = self.sparkle if sparkles else 0.0
        energy = max(level["bass"], level["mid"], level["high"])
        value = base + 0.45 * energy + flash_k * self.flash + 0.5 * spark
        return shade(self.color(self.tone), value, 0.8 * spark, self.color(1.0))

    def tempo_frame(self, level, new_beat, now, dt):
        """Цвет меняется ровно в темп: свои «часы», которые подстраиваются под удары бочки."""
        bpm = level.get("bpm") or 0
        if bpm < 60:  # темп ещё не понятен — работаем как «Бит»
            if new_beat:
                self.pos += 0.382
                self.tick_flash = 1.0
        else:
            period = 60 / bpm
            if self.next_tick is None or self.next_tick - now > 2 * period or now - self.next_tick > 2 * period:
                self.next_tick = now + period
            if new_beat:  # подтягиваем фазу к настоящему удару
                k = round((now - self.next_tick) / period)
                diff = now - (self.next_tick + k * period)
                if abs(diff) < 0.3 * period:
                    self.next_tick += diff * 0.3
            if now >= self.next_tick:
                self.next_tick += period
                self.pos += 0.382  # «золотой» шаг: цвета не повторяются подряд
                self.tick_flash = 1.0
            dt_decay = dt / (0.7 * period)
            self.tick_flash = max(0.0, self.tick_flash - dt_decay)
            return shade(self.color(pingpong(self.pos)), 0.12 + 0.88 * self.tick_flash ** 1.5)
        self.tick_flash = max(0.0, self.tick_flash - dt * 2.5)
        return shade(self.color(pingpong(self.pos)), 0.12 + 0.88 * self.tick_flash ** 1.5)

    def calm_frame(self, level, dt):
        """Медленное дыхание: яркость плавно следует за громкостью, цвет не спеша переливается."""
        energy = max(level["bass"], level["mid"])
        self.calm_level += (energy - self.calm_level) * min(1.0, dt * 0.8)  # реагирует за ~1.5 с
        self.pos += dt * 0.015
        return shade(self.color(pingpong(self.pos)), 0.15 + 0.7 * self.calm_level)

    def screen_frame(self, dt):
        """Цвет экрана, плавно (без мерцания при смене кадров)."""
        target = self.state.screen_rgb
        k = min(1.0, dt * 5)
        self.screen_rgb = tuple(a + (b - a) * k for a, b in zip(self.screen_rgb, target))
        return tuple(int(255 * v) for v in self.screen_rgb)

    # ---------- готовые эффекты (без музыки) ----------

    def smooth_noise(self, key, now, dt, every, speed, lo=0.0, hi=1.0):
        """Плавно блуждающее случайное число: новая цель каждые `every` секунд, догоняем со скоростью speed."""
        value, target, t_next = self.noise.get(key, (0.5, 0.5, 0.0))
        if now >= t_next:
            target, t_next = self.rng.uniform(lo, hi), now + every * self.rng.uniform(0.5, 1.5)
        value += (target - value) * min(1.0, dt * speed)
        self.noise[key] = (value, target, t_next)
        return value

    def candle_frame(self, now, dt):
        v = 0.45 + 0.35 * self.smooth_noise("candle", now, dt, 0.12, 9)
        if self.rng.random() < dt * 0.35:  # изредка пламя «вздрагивает»
            self.noise["candle"] = (0.0, *self.noise["candle"][1:])
        warm = self.smooth_noise("candle_hue", now, dt, 0.8, 2)
        return shade((1.0, 0.36 + 0.12 * warm, 0.04), v)

    def fire_frame(self, now, dt):
        t = 0.2 + 0.55 * self.smooth_noise("fire_t", now, dt, 0.08, 12)
        v = 0.35 + 0.65 * self.smooth_noise("fire_v", now, dt, 0.06, 14)
        return shade(palette_rgb("Огонь", t), v)

    def storm_frame(self, now, dt):
        if self.next_storm is None:
            self.next_storm = now + self.rng.uniform(1.5, 4)
        if now >= self.next_storm:  # удар молнии: 1–3 быстрые вспышки
            t = now
            for _ in range(self.rng.randint(1, 3)):
                dur = self.rng.uniform(0.06, 0.14)
                self.lightning.append((t, t + dur))
                t += dur + self.rng.uniform(0.05, 0.18)
            self.next_storm = t + self.rng.uniform(3, 12)
        self.lightning = [(a, b) for a, b in self.lightning if b > now]
        for a, b in self.lightning:
            if a <= now:
                return shade((0.75, 0.82, 1.0), 1.0 - 0.5 * (now - a) / (b - a))
        v = 0.1 + 0.08 * self.smooth_noise("storm", now, dt, 1.5, 1)
        return shade((0.08, 0.15, 0.6), v)

    def police_frame(self, now, dt):
        phase = now % 1.2
        side, local = ((1, 0, 0), phase) if phase < 0.6 else ((0, 0.15, 1), phase - 0.6)
        on = local < 0.5 and (local % (0.5 / 3)) < 0.1  # три вспышки по 0.1 с
        return shade(side, 1.0) if on else (0, 0, 0)

    def aurora_frame(self, now, dt):
        pos = 0.5 + 0.5 * math.sin(now * 0.13) * math.cos(now * 0.071)
        stops = AURORA
        x = max(0.0, min(1.0, pos)) * (len(stops) - 1)
        i = min(int(x), len(stops) - 2)
        f = x - i
        rgb = tuple(a + (b - a) * f for a, b in zip(stops[i], stops[i + 1]))
        v = 0.3 + 0.4 * (0.5 + 0.5 * math.sin(now * 0.5 + 2 * math.sin(now * 0.23)))
        return shade(rgb, v)
