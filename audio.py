"""Захват звука компьютера и его анализ: полосы частот, бит, хай-хэты, дропы."""
import threading
import time
from collections import deque

import numpy as np
import pyaudiowpatch as pyaudio

BLOCK = 1024


class Analyzer:
    """Считает громкость по полосам и ловит удары. Работает в потоке звука."""

    def __init__(self, rate, sensitivity):
        self.sens = sensitivity
        freqs = np.fft.rfftfreq(BLOCK, 1 / rate)
        self.bands = {
            "bass": (freqs >= 30) & (freqs < 150),
            "mid": (freqs >= 150) & (freqs < 2000),
            "high": (freqs >= 2000) & (freqs < 10000),
        }
        self.window = np.hanning(BLOCK)
        per_sec = rate / BLOCK  # блоков в секунду (~47)
        self.history = deque(maxlen=int(per_sec))  # ~1 секунда басов
        self.high_history = deque(maxlen=int(per_sec))  # ~1 секунда верхов
        self.loud_history = deque(maxlen=int(per_sec * 3))  # ~3 секунды громкости — для дропов
        self.recent_n = max(1, int(per_sec * 0.25))
        # «центр тяжести» спектра: на какой частоте сейчас основная энергия (в октавах)
        self.cent_mask = (freqs >= 30) & (freqs < 10000)
        self.cent_logf = np.log2(freqs[self.cent_mask])
        self.centroid = 9.0
        self.peak = {k: 1e-6 for k in self.bands}
        self.level = {k: 0.0 for k in self.bands}
        self.loudness = 0.0
        self.last_feed = 0.0
        self.last_beat = self.last_hat = self.last_drop = -100.0
        self.beats = 0  # счётчики событий: растут на каждый удар
        self.hats = 0
        self.drops = 0
        self.lock = threading.Lock()

    def feed(self, mono):
        spectrum = np.abs(np.fft.rfft(mono * self.window))
        energy = {k: float(np.mean(spectrum[m] ** 2)) for k, m in self.bands.items()}
        now = time.monotonic()
        with self.lock:
            self.last_feed = now
            for k, e in energy.items():
                # авто-усиление: пик медленно спадает, уровень = доля от пика
                self.peak[k] = max(e, self.peak[k] * 0.995, 1e-6)
                self.level[k] = min(1.0, (e / self.peak[k]) ** 0.5)
            self.loudness = float(np.sqrt(np.mean(mono**2)))
            loud = self.loudness > 0.002

            avg = np.mean(self.history) if self.history else 0.0
            if (len(self.history) > 10 and energy["bass"] > avg * self.sens and self.level["bass"] > 0.35
                    and now - self.last_beat > 0.12 and loud):
                self.last_beat = now
                self.beats += 1
            self.history.append(energy["bass"])

            high_avg = np.mean(self.high_history) if self.high_history else 0.0
            if (len(self.high_history) > 10 and energy["high"] > high_avg * 1.8 and self.level["high"] > 0.45
                    and now - self.last_hat > 0.08 and loud):
                self.last_hat = now
                self.hats += 1
            self.high_history.append(energy["high"])

            # дроп: после затишья громкость резко выросла в 2+ раза
            self.loud_history.append(self.loudness)
            if len(self.loud_history) == self.loud_history.maxlen and now - self.last_drop > 8:
                hist = list(self.loud_history)
                recent = np.mean(hist[-self.recent_n:])
                before = np.mean(hist[: -self.recent_n * 2])
                if recent > 0.02 and recent > before * 2.0:
                    self.last_drop = now
                    self.drops += 1

            mag = spectrum[self.cent_mask]
            if mag.sum() > 1e-9:
                self.centroid = float(np.sum(mag * self.cent_logf) / np.sum(mag))

    def snapshot(self):
        with self.lock:
            # когда ничего не играет, Windows перестаёт присылать звук — считаем это тишиной
            loud = self.loudness if time.monotonic() - self.last_feed < 0.5 else 0.0
            level = {**self.level, "centroid": self.centroid}
            return level, loud, {"beats": self.beats, "hats": self.hats, "drops": self.drops}


def start_audio(sensitivity):
    """Начинает слушать звук, который идёт в колонки по умолчанию."""
    p = pyaudio.PyAudio()
    dev = p.get_default_wasapi_loopback()
    rate = int(dev["defaultSampleRate"])
    channels = dev["maxInputChannels"]
    analyzer = Analyzer(rate, sensitivity)
    buf = np.zeros(0, dtype=np.float32)

    def callback(data, frames, info, status):
        nonlocal buf
        mono = np.frombuffer(data, dtype=np.float32).reshape(-1, channels).mean(axis=1)
        buf = np.concatenate([buf, mono])
        while buf.size >= BLOCK:  # режем на блоки ровно по BLOCK сэмплов
            analyzer.feed(buf[:BLOCK])
            buf = buf[BLOCK:]
        return (None, pyaudio.paContinue)

    stream = p.open(
        format=pyaudio.paFloat32, channels=channels, rate=rate, input=True,
        input_device_index=dev["index"], frames_per_buffer=BLOCK, stream_callback=callback,
    )
    stream.start_stream()
    print(f"Слушаю звук: {dev['name']}")
    return analyzer, stream, p


def start_audio_in_thread(sensitivity):
    """PyAudio переводит свой поток в режим COM STA, а Bluetooth (bleak) в таком потоке
    не работает, поэтому звук запускаем в отдельном потоке."""
    result = {}
    t = threading.Thread(target=lambda: result.update(audio=start_audio(sensitivity)))
    t.start()
    t.join()
    return result["audio"]
