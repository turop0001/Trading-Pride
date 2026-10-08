"""Красные новости (High impact) USD/EUR/GBP на сегодня по Риге — из календаря ForexFactory
(официальный JSON-фид faireconomy). Результат кладётся в state['_news'] и показывается в Пульте."""
import json, time, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
CUR = ('USD', 'EUR', 'GBP')
RIGA = ZoneInfo('Europe/Riga')


def fetch_today(today):
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode('utf-8'))
    out = []
    for e in data:
        if e.get('impact') != 'High' or e.get('country') not in CUR: continue
        try: d = dt.datetime.fromisoformat(e['date']).astimezone(RIGA)
        except Exception: continue
        if d.strftime('%Y-%m-%d') != today: continue
        out.append({'t': d.strftime('%H:%M'), 'cur': e['country'], 'title': e.get('title', '')})
    out.sort(key=lambda x: x['t'])
    return out


def refresh(state, today, max_age=3600):
    """Обновляет state['_news'] не чаще раза в час (фид с лимитами). Ошибки не ломают тик."""
    n = state.get('_news') or {}
    if n.get('date') == today and time.time() - n.get('at', 0) < max_age: return False
    try:
        items = fetch_today(today)
    except Exception as e:
        print('news failed:', e)
        if n.get('date') == today: return False
        state['_news'] = {'date': today, 'at': time.time() - max_age + 300, 'items': [], 'err': True}
        return True
    state['_news'] = {'date': today, 'at': time.time(), 'items': items}
    return True
