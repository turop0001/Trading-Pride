#!/usr/bin/env python3
"""Разовый тест: недельный отчёт (картинка + текст одним сообщением) по данным последней недели из state/history.json,
с пометкой ТЕСТ. Состояние не трогает."""
import sys, os, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_check as lc
import notify, report_image as ri

riga, _ = lc.riga_now()
mon = riga.date() - dt.timedelta(days=riga.weekday())
items = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'history.json'), encoding='utf-8'))
text = '\U0001F9EA ТЕСТ (картинка + текст одним сообщением)\n' + notify.build_weekly(mon, mon + dt.timedelta(days=4), items)
print('длина подписи:', len(ri.fit_caption(text)))
print('отправлено:', ri.send_report(text, ri.week_data(mon, mon + dt.timedelta(days=4), items), 'test'))
