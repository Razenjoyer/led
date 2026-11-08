"""Проверка звука: 8 секунд печатает уровни и число найденных битов."""
import time

import led_music as m

a, s, p = m.start_audio(1.4)
for _ in range(8):
    time.sleep(1)
    lv, loud, beats = a.snapshot()
    print(f"громкость={loud:.4f} басы={lv['bass']:.2f} середина={lv['mid']:.2f} верха={lv['high']:.2f} битов={beats}")
s.stop_stream()
s.close()
p.terminate()
