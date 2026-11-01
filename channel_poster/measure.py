#!/usr/bin/env python3
"""Замер активности и вовлечённости публичных Telegram-каналов (t.me/s/<name>).
Метрики: постов в сутки, средние/медианные просмотры «устоявшихся» постов (старше 6 ч), охват = просмотры/подписчики.
Запуск: python3 measure.py имя1 имя2 ...  (или без аргументов — берёт sources.json + candidates.txt). Вывод JSON в measure_out.json."""
import re, sys, json, html, statistics as st, datetime as dt, urllib.request, concurrent.futures as cf
H = {'User-Agent': 'Mozilla/5.0'}

def get(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=15).read().decode('utf-8', 'replace')
    except Exception:
        return ''

def num(s):
    s = (s or '').replace('\xa0', '').replace(' ', '').replace(',', '.').strip()
    try:
        if s[-1:] in 'Kk': return int(float(s[:-1]) * 1000)
        if s[-1:] in 'Mm': return int(float(s[:-1]) * 1000000)
        return int(float(s))
    except Exception: return 0

def measure(u):
    pg = get('https://t.me/s/' + u)
    r = {'u': u, 'ok': False}
    if 'tgme_widget_message_wrap' not in pg: return r
    top = get('https://t.me/' + u)
    m = re.search(r'tgme_page_extra">\s*([\d\s\xa0.,KkMm]+)\s*(?:subscribers|подписчик)', top)
    subs = num(m.group(1)) if m else 0
    now = dt.datetime.now(dt.timezone.utc); posts = []
    for blk in pg.split('tgme_widget_message_wrap')[1:]:
        d = re.search(r'datetime="([^"]+)"', blk); v = re.search(r'tgme_widget_message_views">([^<]+)<', blk)
        t = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S)
        if not d: continue
        try: when = dt.datetime.fromisoformat(d.group(1))
        except Exception: continue
        tx = ''
        if t:
            tx = re.sub(r'<[^>]+>', ' ', re.sub(r'<br\s*/?>', ' ', t.group(1))); tx = re.sub(r'\s+', ' ', html.unescape(tx)).strip()
        posts.append((when, num(v.group(1)) if v else 0, tx))
    if len(posts) < 3: return r
    posts.sort(); span = max((posts[-1][0] - posts[0][0]).total_seconds() / 86400, 0.05)
    age_last = (now - posts[-1][0]).total_seconds() / 3600
    settled = [p[1] for p in posts if (now - p[0]).total_seconds() > 6 * 3600 and p[1] > 0] or [p[1] for p in posts if p[1] > 0]
    avg = int(st.mean(settled)) if settled else 0; med = int(st.median(settled)) if settled else 0
    r.update(ok=True, subs=subs, per_day=round((len(posts) - 1) / span, 1), last_h=round(age_last, 1), avg=avg, med=med,
             er=round(100.0 * med / subs, 1) if subs else None, n=len(posts),
             sample=[p[2][:110] for p in posts[-3:] if p[2]])
    return r

if __name__ == '__main__':
    names = sys.argv[1:]
    if not names:
        names = [c['u'] for c in json.load(open('sources.json', encoding='utf-8'))['channels']]
        try: names += [x.strip() for x in open('candidates.txt') if x.strip()]
        except Exception: pass
    names = list(dict.fromkeys(names))
    with cf.ThreadPoolExecutor(8) as ex: res = list(ex.map(measure, names))
    json.dump(res, open('measure_out.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for r in sorted([x for x in res if x['ok']], key=lambda x: -(x['med'] or 0)):
        print('%-26s подп %-8s пост/сут %-5s посл %-5sч просм(мед) %-7s охват %s%%' % (r['u'], r['subs'], r['per_day'], r['last_h'], r['med'], r['er']))
    print('не читаются/нет:', [x['u'] for x in res if not x['ok']])
