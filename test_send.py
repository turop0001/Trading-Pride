#!/usr/bin/env python3
"""Разовый тест доставки Telegram через GitHub Actions (не трогает production pult_tick.py).
Берёт последние сохранённые в state/pult_state.json данные (последний торговый день) и шлёт
отчёт дня с явной пометкой ТЕСТ — проверяем, что секреты/сеть/GitHub Actions -> Telegram
работают end-to-end, независимо от того, открыто сейчас торговое окно или нет."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_check as lc
from notify import build_daily_summary, send_telegram, fmt_line

state = lc.load_state()
WINDOW_SYMBOLS = lc.WINDOW_SYMBOLS


def result_of(res):
    n, pct = 0, 0.0
    for r in res.values():
        if r.get('signal'):
            n += 1
            if 'TP' in r.get('note', ''):
                pct += 2.0
            elif 'SL' in r.get('note', ''):
                pct -= 1.0
    return n, pct


def lines_for(win, res):
    out = []
    for s in WINDOW_SYMBOLS[win] + (['GER40'] if win == 'A' else []):
        r = res.get(s)
        if r:
            out.append(fmt_line(r.get('line_status'), s, r.get('direction'), r.get('tg_note') or r.get('note', '')))
    return out


dates = set()
for k, v in state.items():
    if isinstance(v, dict) and v.get('date'):
        dates.add(v['date'])
last_date = max(dates) if dates else None

if not last_date:
    print('Нет сохранённых данных для теста — state пуст')
    sys.exit(0)

sections, total = [], 0.0
for w in ('A', 'C'):
    res = {s: state.get(f'{s}_{w}', {}) for s in WINDOW_SYMBOLS[w] if state.get(f'{s}_{w}', {}).get('date') == last_date}
    if not res:
        continue
    n, pct = result_of(res)
    total += pct
    sections.append((w, lines_for(w, res), []))

if not sections:
    print('Нет секций для последней даты', last_date)
    sys.exit(0)

try:
    y, m, d = last_date.split('-')
    dstr = f'{d}.{m}.{y}'
except Exception:
    dstr = last_date

txt = build_daily_summary(dstr, sections, total)
txt = '🧪 ТЕСТ ДОСТАВКИ (проверка GitHub Actions → Telegram, данные не новые, реального сигнала нет)\n\n' + txt
ok = send_telegram(txt)
print('SENT:', ok, 'date:', last_date)
