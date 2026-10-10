"""Первичное наполнение state/analytics.json: последние 10 сделок A и 10 сделок C повтором движка на архивных данных
(+ свежие файлы _bt/_data/nd/<SYM>.csv). Использование: python3 seed_analytics.py [последний_день YYYY-MM-DD]"""
import sys, os, datetime as dt, pandas as pd
import analytics_gen as AG
BASE = os.path.expanduser('~/mnt/Work/Trading System/_bt/_data/')
last = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date(2026, 10, 9)
SYMS = {'A': ['XAUUSD', 'EURUSD', 'GBPUSD', 'GER40', 'NAS100', 'US30', 'US500'], 'C': ['XAUUSD', 'EURUSD', 'GBPUSD']}


def load(s):
    a = pd.read_csv(BASE + '%s_5y_M5.csv.gz' % s, parse_dates=['timestamp']).set_index('timestamp')
    p = BASE + 'nd/%s.csv' % s
    if os.path.exists(p):
        b = pd.read_csv(p, header=None, names=['timestamp', 'Open', 'High', 'Low', 'Close'], parse_dates=['timestamp']).set_index('timestamp')
        a = pd.concat([a, b])
    a = a[~a.index.duplicated(keep='last')].sort_index()[['Open', 'High', 'Low', 'Close']]
    cut = pd.Timestamp(last, tz='UTC') - pd.Timedelta(days=120)   # хватает на глубину поиска
    return a[a.index >= cut]


D = {s: load(s) for s in SYMS['A']}
print({s: str(D[s].index[-1]) for s in D})
out = {}
for typ in ('A', 'C'):
    recs = AG.replay(typ, {s: D[s] for s in SYMS[typ]}, last, 10)
    out[typ] = recs
    print(typ, len(recs), [(r['day'], r['sym'], r['res']) for r in recs])
import json
os.makedirs('state', exist_ok=True)
json.dump(out, open('state/analytics.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('saved', os.path.getsize('state/analytics.json'))
