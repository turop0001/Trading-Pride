"""Push-уведомления на телефон/компьютер при закрытой странице (08.10.2026).
Подписки лежат в ветке feed (feed/push.json, пишет /api/push на Vercel). Ключ VAPID_PRIVATE_KEY — секрет GitHub Actions;
если его нет или подписок нет — функция тихо ничего не делает (Telegram и Пульт работают как раньше)."""
import os, json, urllib.request

SUBJECT = os.environ.get('VAPID_SUBJECT', 'mailto:dmitriybarinov1@gmail.com')
URL = 'https://api.github.com/repos/turop0001/Trading-Pride/contents/feed/push.json?ref=feed'
SITE = os.environ.get('PULT_SITE', 'https://trading-pride-three.vercel.app')
_cache = {'t': 0, 'subs': []}


def _subs():
    import time
    if time.time() - _cache['t'] < 60: return _cache['subs']
    _cache['t'] = time.time()
    try:
        h = {'Accept': 'application/vnd.github.raw', 'User-Agent': 'pult'}
        tok = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if tok: h['Authorization'] = f'Bearer {tok}'
        _cache['subs'] = (json.load(urllib.request.urlopen(urllib.request.Request(URL, headers=h), timeout=15)) or {}).get('subs') or []
    except Exception as e:
        print('push subs недоступны:', str(e)[:100]); _cache['subs'] = []
    return _cache['subs']


def notify(title, body, tag=None, sticky=False):
    key = os.environ.get('VAPID_PRIVATE_KEY', '').strip()
    if not key: return 0
    subs = _subs()
    if not subs: return 0
    try:
        from pywebpush import webpush
    except Exception as e:
        print('pywebpush нет:', e); return 0
    n = 0
    for s in subs:
        try:
            webpush(subscription_info={'endpoint': s['endpoint'], 'keys': s['keys']},
                    data=json.dumps({'title': title, 'body': body, 'tag': tag, 'sticky': sticky, 'url': '/'}, ensure_ascii=False),
                    vapid_private_key=key, vapid_claims={'sub': SUBJECT}, ttl=600)
            n += 1
        except Exception as e:
            print('push не доставлен:', str(e)[:120])
    return n
