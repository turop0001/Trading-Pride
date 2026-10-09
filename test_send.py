#!/usr/bin/env python3
"""Разовый тест доставки Telegram через GitHub Actions (не трогает production pult_tick.py).
ВАЖНО: считает статусы ЗАНОВО текущим кодом (live_check.check_instrument -> pult_rules.analyze)
по свежим данным — не берёт старые закэшированные строки из state/pult_state.json, которые
могли быть посчитаны ДО последних правок (например когда ещё было слово "bias" в тексте).
Шлёт с явной пометкой ТЕСТ."""
import sys, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_check as lc
from notify import send_telegram, fmt_line

riga, off = lc.riga_now()
today_str = riga.strftime('%d.%m.%Y')

sections = []
for w in ('A', 'C'):
    lines = []
    for sym in lc.WINDOW_SYMBOLS[w]:
        r = lc.check_instrument(sym, lc.ticker_for(sym, w), w, prev={})
        if r.get('error'):
            lines.append(f"⚪ {sym} — ошибка данных ({r['error']})")
            continue
        ls = r.get('line_status')
        note = r.get('tg_note') or r.get('note', '')
        lines.append(fmt_line(ls, sym, r.get('direction'), note))
    sections.append((w, lines))

out = [f"🧪 ТЕСТ ДОСТАВКИ (проверка GitHub Actions → Telegram, статусы посчитаны заново текущим кодом, без bias/лишних комментариев)\n"]
out.append(f"📊 Живой срез · {today_str} ({riga.strftime('%H:%M')} UTC+3)\n")
for w, lines in sections:
    out.append(f"Тип {w}:")
    out.extend(lines)
    out.append("")
txt = "\n".join(out)

ok = send_telegram(txt)
print('SENT:', ok)
