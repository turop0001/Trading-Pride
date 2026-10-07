"""Сторожок цикла Пульта (07.10.2026): если в окне A (10:00–14:00) или C (16:30–18:30 Рига) минутный цикл
(loop.yml) не работает — запускает его заново. GitHub-расписание бывает пропущено целиком (07.10: цикл окна C
не стартовал, отчёт открытия пришёл на 48 минут позже), поэтому сторожок вызывается из 5-минутного тика
и дополнительно из /api/feed (MT5 шлёт свечи раз в минуту — независимо от GitHub и от Claude)."""
import os, json, urllib.request, urllib.error, datetime as dt, zoneinfo

REPO = os.environ.get('GITHUB_REPOSITORY', 'turop0001/Trading-Pride')
TOK = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or ''


def api(path, method='GET', body=None):
    rq = urllib.request.Request('https://api.github.com' + path, method=method,
                                data=None if body is None else json.dumps(body).encode(),
                                headers={'Authorization': 'Bearer ' + TOK, 'Accept': 'application/vnd.github+json',
                                         'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(rq, timeout=15) as r:
        t = r.read().decode()
        return r.status, (json.loads(t) if t else {})


def in_window(riga):
    if riga.weekday() >= 5: return False
    m = riga.hour * 60 + riga.minute
    return 590 <= m <= 840 or 980 <= m <= 1110     # A: 09:50–14:00, C: 16:20–18:30


def tg(text):
    tk, ch = os.environ.get('TG_BOT_TOKEN'), os.environ.get('TG_CHAT_ID')
    if not (tk and ch): return
    b = {'chat_id': ch, 'text': text}
    if os.environ.get('TG_THREAD_ID'): b['message_thread_id'] = int(os.environ['TG_THREAD_ID'])
    try:
        urllib.request.urlopen(urllib.request.Request(f'https://api.telegram.org/bot{tk}/sendMessage', data=json.dumps(b).encode(),
                               headers={'Content-Type': 'application/json'}), timeout=10)
    except Exception:
        pass


def main():
    riga = dt.datetime.now(zoneinfo.ZoneInfo('Europe/Riga'))
    if not in_window(riga) or not TOK:
        return 'вне окна'
    for st in ('in_progress', 'queued'):
        _, d = api(f'/repos/{REPO}/actions/workflows/loop.yml/runs?status={st}&per_page=3')
        if d.get('workflow_runs'):
            return 'цикл работает'
    api(f'/repos/{REPO}/actions/workflows/loop.yml/dispatches', 'POST', {'ref': 'main'})
    tg('⚠️ Минутный цикл Пульта не работал в окне — перезапущен автоматически (' + riga.strftime('%H:%M') + ' Рига).')
    return 'перезапущен'


if __name__ == '__main__':
    try:
        print('watchdog:', main())
    except Exception as e:      # сторожок не должен ронять тик
        print('watchdog error:', e)
