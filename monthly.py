#!/usr/bin/env python3
"""Итоги месяца в Telegram (картинка + текст одним сообщением) — запуск 1-го числа из monthly.yml
(включая выходные; в будни то же самое делает pult_tick.py). Флаг state['_monthly'] — без дублей."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_check as lc
import report_image as ri

riga, off = lc.riga_now()
state = lc.load_state()
try:
    items = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'history.json'), encoding='utf-8'))
except Exception:
    items = []
if ri.maybe_send_monthly(state, riga, items, send='--no-send' not in sys.argv, force='--force' in sys.argv):
    lc.save_state(state)
    print('monthly: отправлено')
else:
    print('monthly: сегодня не требуется')
