#!/usr/bin/env python3
"""Повторная отправка недельного отчёта за последнюю завершённую неделю: картинка + подпись из двух строк.
Состояние (_weekly) не трогает. Запуск: workflow «Resend weekly report» (вручную)."""
import sys, os, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_check as lc
import notify, report_image as ri

riga, _ = lc.riga_now()
d = riga.date()
mon = d - dt.timedelta(days=d.weekday()) if d.weekday() >= 4 else d - dt.timedelta(days=d.weekday() + 7)
fri = mon + dt.timedelta(days=4)
items = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'history.json'), encoding='utf-8'))
text = notify.build_weekly(mon, fri, items)
print('отправлено:', ri.send_report(text, ri.week_data(mon, fri, items), 'weekly', caption='\n'.join(text.split('\n')[:2])))
