"""28.10.2026: новая аналитика по правилам A v2.03 / C v1.11 (последние 10 сделок каждого типа повтором движка на истории),
старая аналитика уходит в ключи A_arch / C_arch (показывается внизу вкладки «Аналитика» как архив).
Использование: python3 seed_analytics_v2.py <D5.pkl> [последний_день YYYY-MM-DD]"""
import sys, os, json, pickle, datetime as dt
import analytics_gen as AG
pk = sys.argv[1]; last = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date(2026, 10, 23)
D = pickle.load(open(pk, 'rb'))
SYMS = {'A': ['EURUSD', 'GBPUSD', 'US500', 'GER40', 'AUDUSD', 'UK100', 'NAS100', 'US30', 'USDJPY'], 'C': ['GBPUSD', 'US500', 'GER40', 'UK100']}
old = AG.load(AG.PATH)
out = {'A_arch': old.get('A_arch') or old['A'], 'C_arch': old.get('C_arch') or old['C']}
for typ in ('A', 'C'):
    recs = AG.replay(typ, {s: D[s] for s in SYMS[typ]}, last, 10)
    out[typ] = recs
    print(typ, len(recs), [(r['day'], r['sym'], r['res'], r['R']) for r in recs])
json.dump(out, open(AG.PATH, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('saved', os.path.getsize(AG.PATH), {k: len(v) for k, v in out.items()})
