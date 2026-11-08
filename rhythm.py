"""Темп песни (BPM) и поиск припева. Работают на «блоках» звука (~47 в секунду)."""
import math
from collections import deque

import numpy as np


class TempoTracker:
    """Темп по автокорреляции «ударности» звука за последние ~8 секунд."""

    def __init__(self, per_sec, seconds=8.0):
        self.per_sec = per_sec
        self.onsets = deque(maxlen=int(per_sec * seconds))
        self.prev = None
        self.blocks = 0
        self.bpm = 0.0
        self.confidence = 0.0
        self.candidate = 0.0
        lo = max(2, int(per_sec * 60 / 190))  # от 190 BPM
        hi = int(math.ceil(per_sec * 60 / 65))  # до 65 BPM
        self.lags = np.arange(lo, hi + 1)
        # большинство песен 85–170 BPM: мягко предпочитаем этот диапазон, чтобы не путать темп с половинным/двойным
        bpms = 60 * per_sec / self.lags
        self.weight = np.exp(-0.5 * (np.log2(bpms / 120) / 0.9) ** 2)

    def add(self, bass_energy, mid_energy):
        level = math.log(bass_energy * 2 + mid_energy + 1e-12)
        flux = 0.0 if self.prev is None else max(0.0, level - self.prev)
        self.prev = level
        self.onsets.append(flux)
        self.blocks += 1
        if self.blocks % max(1, int(self.per_sec / 2)) == 0:  # пересчитываем дважды в секунду
            self.estimate()

    def estimate(self):
        if len(self.onsets) < self.per_sec * 4:
            return
        x = np.asarray(self.onsets) - np.mean(self.onsets)
        energy = float(np.dot(x, x))
        if energy <= 1e-12:
            return
        n = len(x)
        ac = np.array([np.dot(x[:-lag], x[lag:]) / energy * n / (n - lag) for lag in self.lags])
        i = int(np.argmax(ac * self.weight))
        conf = float(ac[i])
        if conf < 0.08:
            self.confidence *= 0.9
            return
        lag = float(self.lags[i])
        if 0 < i < len(ac) - 1:  # уточняем пик параболой — дробная задержка
            a, b, c = ac[i - 1], ac[i], ac[i + 1]
            d = a - 2 * b + c
            if d < 0:
                lag += 0.5 * (a - c) / d
        bpm = 60 * self.per_sec / lag
        if self.bpm and abs(bpm - self.bpm) / self.bpm < 0.05:
            self.bpm = 0.8 * self.bpm + 0.2 * bpm  # тот же темп — сглаживаем
        elif self.candidate and abs(bpm - self.candidate) / self.candidate < 0.05:
            self.bpm = bpm  # новый темп подтвердился дважды подряд — принимаем
        self.candidate = bpm
        self.confidence = conf


class ChorusDetector:
    """Припев/кульминация: громкость за последние ~3 с заметно выше средней по песне (~25 с)."""

    def __init__(self, per_sec, enter=1.3, leave=1.08, hold_s=4.0, warmup_s=8.0):
        self.per_sec = per_sec
        self.a_short = 1 / (per_sec * 3)
        self.a_long = 1 / (per_sec * 25)
        self.enter, self.leave = enter, leave
        self.hold = int(per_sec * hold_s)
        self.warmup = int(per_sec * warmup_s)
        self.short = self.long = 0.0
        self.blocks = 0
        self.since_change = 0
        self.active = False

    def add(self, loudness):
        self.blocks += 1
        self.since_change += 1
        # в начале — честное среднее по всем блокам, чтобы один громкий первый удар не исказил «норму»
        self.short += (loudness - self.short) * max(self.a_short, 1 / self.blocks)
        self.long += (loudness - self.long) * max(self.a_long, 1 / self.blocks)
        if self.blocks < self.warmup or self.since_change < self.hold:
            return
        if not self.active and self.short > self.long * self.enter and self.short > 0.01:
            self.active, self.since_change = True, 0
        elif self.active and self.short < self.long * self.leave:
            self.active, self.since_change = False, 0
