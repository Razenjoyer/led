"""Световые эффекты: из звука (или экрана) получаем цвет ленты."""
import random
import time

from palettes import palette_rgb, pingpong, shade

MODES = ["manual", "freq", "beat", "pulse", "calm", "spectrum", "screen"]
MODE_LABELS = {
    "manual": "Ручной цвет",
    "freq": "Частоты — басы тёплые, верха холодные",
    "beat": "Бит — новый цвет на каждый удар",
    "pulse": "Пульс — яркость от басов",
    "calm": "Плавный — спокойное дыхание без вспышек",
    "spectrum": "Спектр — басы/середина/верха = R/G/B",
    "screen": "Экран — цвет того, что на мониторе",
}
MUSIC_MODES = {"freq", "beat", "pulse", "calm", "spectrum"}
STROBE_SECONDS = 1.2


class Effects:
    def __init__(self, state):
        self.state = state
        self.pos = random.random()  # позиция в палитре для «Бита», «Пульса», «Плавного» и тишины
        self.flash = 0.0
        self.sparkle = 0.0
        self.seen = {"beats": 0, "hats": 0, "drops": 0}
        self.quiet_since = None
        self.tone = 0.5  # 0 — басы (начало палитры), 1 — верха (конец), сглаженно
        self.lo, self.hi = 8.0, 11.0  # границы «центра тяжести» спектра для этой песни, в октавах
        self.calm_level = 0.3
        self.strobe_until = 0.0
        self.screen_rgb = (0.0, 0.0, 0.0)

    def color(self, t):
        return palette_rgb(self.state.palette, t)

    def frame(self, level, loudness, events, dt):
        mode = self.state.mode
        if mode == "manual":
            return self.state.color
        if mode == "screen":
            return self.screen_frame(dt)

        now = time.monotonic()
        if loudness < 0.0015:
            self.quiet_since = self.quiet_since or now
        else:
            self.quiet_since = None
        if self.quiet_since and now - self.quiet_since > 2:
            # тишина: медленно переливаемся тусклыми цветами палитры
            self.pos += dt * 0.02
            return shade(self.color(pingpong(self.pos)), 0.08)

        new = {k: events[k] != self.seen[k] for k in self.seen}
        self.seen = dict(events)
        self.flash = max(0.0, self.flash - dt * 4)  # вспышка гаснет за ~0.25 с
        self.sparkle = max(0.0, self.sparkle - dt * 7)  # искра гаснет за ~0.15 с

        # стробоскоп на дропе: ~12 вспышек в секунду цветом верхов палитры
        if new["drops"] and self.state.strobe and mode != "calm":
            self.strobe_until = now + STROBE_SECONDS
        if now < self.strobe_until:
            on = int((self.strobe_until - now) * 12.5) % 2 == 0
            return shade(self.color(1.0), 1.0) if on else (0, 0, 0)

        if mode == "freq":
            return self.freq_frame(level, new["beats"], new["hats"], dt)
        if mode == "spectrum":
            return tuple(int(255 * v) for v in (level["bass"], level["mid"] * 0.8, level["high"]))
        if mode == "pulse":
            self.pos += dt * 0.05
            return shade(self.color(pingpong(self.pos)), 0.1 + 0.9 * level["bass"] ** 1.5)
        if mode == "calm":
            return self.calm_frame(level, dt)

        # beat: на каждый удар новый цвет из палитры и вспышка
        if new["beats"]:
            self.pos += random.uniform(0.2, 0.45)
            self.flash = 1.0
        base = 0.15 + 0.25 * level["mid"]
        return shade(self.color(pingpong(self.pos)), base + self.flash * 0.85)

    def freq_frame(self, level, new_beat, new_hat, dt):
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
        self.tone += (target - self.tone) * min(1.0, dt * 6)  # плавный переход ~0.2 с
        if new_beat:
            self.flash = 1.0
            self.tone *= 0.4  # удар бочки тянет цвет к басовому
        if new_hat:
            self.sparkle = 1.0
        energy = max(level["bass"], level["mid"], level["high"])
        value = 0.2 + 0.45 * energy + 0.6 * self.flash + 0.5 * self.sparkle
        return shade(self.color(self.tone), value, 0.8 * self.sparkle, self.color(1.0))

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
