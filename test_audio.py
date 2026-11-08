"""Проверка живого звука: 12 секунд печатает громкость, темп и число ударов."""
import time

import audio

a, s, p = audio.start_audio(1.4)
for i in range(12):
    time.sleep(1)
    lv, loud, ev = a.snapshot()
    if i % 3 == 2:
        print(f"{i + 1:2d} с: громкость={loud:.4f} басы={lv['bass']:.2f} темп={lv['bpm']:.1f} "
              f"уверенность={a.tempo.confidence:.2f} ударов={ev['beats']} припев={lv['chorus']}")
s.stop_stream()
s.close()
p.terminate()
