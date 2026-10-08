#!/usr/bin/env python3
"""Картинка недельного / месячного отчёта для Telegram (дизайн утверждён 08.10.2026) +
отправка «картинка + текст одним сообщением» (sendPhoto, подпись ≤ 1024 символов).

Рендер: HTML-шаблон report_assets/template.html → скриншот headless-браузером (Chrome есть на
GitHub-раннере ubuntu-latest; шрифт Carlito и логотип лежат в report_assets/, чтобы вид не зависел
от системы). Любая ошибка рендера/отправки фото → запасной вариант: обычное текстовое сообщение.
Источник данных тот же, что у текстового отчёта: state/history.json (notify._weekly_parse).
"""
import os, re, json, glob, shutil, subprocess, tempfile, datetime as dt, urllib.request, urllib.parse
import notify

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'report_assets')
WD = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']


def _trades(items, d0, d1):
    """{'YYYY-MM-DD': {'A': [(out, r)], 'C': [...]}} за период d0..d1 (включительно, строки дат)."""
    res = {}
    for it in sorted(items, key=lambda x: (x.get('date') or '', x.get('symbol') or '')):
        d = it.get('date') or ''
        t = it.get('type')
        if not (d0 <= d <= d1) or t not in ('A', 'C'):
            continue
        p = notify._weekly_parse(it)
        if not p:
            continue
        res.setdefault(d, {'A': [], 'C': []})[t].append((p[0], p[1]))
    return res


def _stat(lst):
    n = len(lst); tp = sum(1 for o, _ in lst if o == 'TP'); sl = sum(1 for o, _ in lst if o == 'SL')
    return {'n': n, 'tp': tp, 'sl': sl, 'be': n - tp - sl, 'r': round(sum(r for _, r in lst), 2),
            'wr': round(tp / n * 100) if n else 0}


def _row(l, s, days, tr):
    A = [x for d in days for x in tr.get(d, {}).get('A', [])]
    C = [x for d in days for x in tr.get(d, {}).get('C', [])]
    return {'l': l, 's': s, 'A': [list(x) for x in A], 'C': [list(x) for x in C],
            'tot': round(sum(r for _, r in A + C), 2)}


def _finish(data, tr):
    allA = [x for d in tr.values() for x in d['A']]
    allC = [x for d in tr.values() for x in d['C']]
    data['A'], data['C'], data['total'] = _stat(allA), _stat(allC), _stat(allA + allC)
    return data


def week_data(mon, fri, items):
    tr = _trades(items, str(mon), str(fri))
    rows = []
    for i in range(5):
        d = mon + dt.timedelta(days=i)
        rows.append(_row(WD[i], d.strftime('%d.%m'), [str(d)], tr))
    data = {'small': 'WEEKLY REPORT', 'h1': 'Итоги недели', 'sec': 'По дням', 'col': 'Итог дня',
            'per': 'НЕДЕЛЯ', 'agg': False, 'rows': rows,
            'dates': f"{mon.strftime('%d.%m')} – {fri.strftime('%d.%m.%Y')}"}
    return _finish(data, tr)


def month_data(year, month, items):
    first = dt.date(year, month, 1)
    last = (dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1))
    tr = _trades(items, str(first), str(last))
    rows, d, k = [], first, 1
    while d <= last:
        wk_end = min(d + dt.timedelta(days=6 - d.weekday()), last)
        days = [str(d + dt.timedelta(days=i)) for i in range((wk_end - d).days + 1)]
        if d.weekday() < 5:
            fe = min(wk_end, d + dt.timedelta(days=4 - d.weekday()))   # конец подписи — последний будний день
            lab = f"{d.strftime('%d')}\u2013{fe.strftime('%d.%m')}" if d != fe else d.strftime('%d.%m')
            rows.append(_row(f'Нед {k}', lab, days, tr)); k += 1
        d = wk_end + dt.timedelta(days=1)
    data = {'small': 'MONTHLY REPORT', 'h1': 'Итоги месяца', 'sec': 'По неделям', 'col': 'Итог недели',
            'per': 'МЕСЯЦ', 'agg': True, 'rows': rows, 'dates': f'{MONTHS[month - 1]} {year}'}
    return _finish(data, tr)


# ---------------- рендер ----------------
def _browser():
    cands = [os.environ.get('REPORT_BROWSER', '')] + [shutil.which(x) or '' for x in
             ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome')]
    cands += sorted(glob.glob('/opt/pw-browsers/chromium-*/chrome-linux*/chrome'))
    cands += ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def render(data, out_png):
    """Сохраняет PNG 1080×1350. True/False."""
    br = _browser()
    if not br:
        print('report_image: браузер не найден'); return False
    tpl = open(os.path.join(ASSETS, 'template.html'), encoding='utf-8').read()
    tpl = tpl.replace('{{ASSETS}}', 'file://' + ASSETS).replace('/*DATA*/null', json.dumps(data, ensure_ascii=False))
    tmp = tempfile.mkdtemp(prefix='rep_')
    try:
        html = os.path.join(tmp, 'r.html')
        open(html, 'w', encoding='utf-8').write(tpl)
        cmd = [br, '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
               '--force-device-scale-factor=1', '--window-size=1080,1700', '--virtual-time-budget=3000',
               '--allow-file-access-from-files', f'--user-data-dir={tmp}/prof', f'--screenshot={out_png}',
               'file://' + html]
        subprocess.run(cmd, capture_output=True, timeout=90)
        if not (os.path.exists(out_png) and os.path.getsize(out_png) > 20000):
            print('report_image: скриншот не получен'); return False
        from PIL import Image   # окно берём с запасом по высоте и обрезаем ровно до 1080×1350
        im = Image.open(out_png).convert('RGB')
        c = Image.new('RGB', (1080, 1350), (6, 8, 12)); c.paste(im.crop((0, 0, 1080, 1350)), (0, 0)); c.save(out_png)
        return True
    except Exception as e:
        print('report_image: ошибка рендера:', e); return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------- отправка ----------------
def fit_caption(text, limit=1000):
    """Подпись к фото ≤ лимита: если длинная — убираем построчный список сделок, оставляя итоги."""
    if len(text) <= limit:
        return text
    lines = [l for l in text.split('\n') if not re.match(r'^\S+ \d\d\.\d\d \S+ \(', l)]
    t = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines))
    return t if len(t) <= limit else t[:limit - 1].rstrip() + '…'


def send_report(text, data, name='report'):
    """Картинка + текст ОДНИМ сообщением. При любой неудаче — обычный текст (как раньше)."""
    try:
        png = os.path.join(tempfile.gettempdir(), f'{name}.png')
        if render(data, png) and notify.send_telegram_photo(png, fit_caption(text)):
            return True
    except Exception as e:
        print('report_image: фото не ушло:', e)
    return notify.send_telegram(text)


if __name__ == '__main__':   # python report_image.py week|month out.png  (тест рендера из state/history.json)
    import sys
    items = json.load(open(os.path.join(HERE, 'state', 'history.json'), encoding='utf-8'))
    if sys.argv[1] == 'week':
        d = dt.date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else dt.date.today()
        mon = d - dt.timedelta(days=d.weekday()); data = week_data(mon, mon + dt.timedelta(days=4), items)
    else:
        y, m = (int(x) for x in sys.argv[3].split('-')); data = month_data(y, m, items)
    print(render(data, sys.argv[2]))


def maybe_send_monthly(state, riga, items, send=True, force=False):
    """Итоги месяца — 1-го числа (за прошлый месяц), картинка + текст одним сообщением.
    Срабатывает с 10:00 Рига 1-го числа (если 1-е выпало на выходной — в первый запуск с 1 по 3 число).
    Флаг state['_monthly'] защищает от повторной отправки. Возвращает True, если отправлено."""
    prev = riga.replace(day=1) - dt.timedelta(days=1)
    key = prev.strftime('%Y-%m')
    if not force:
        if riga.day > 3 or riga.hour * 60 + riga.minute < 600:
            return False
        if (state.get('_monthly') or {}).get('month') == key:
            return False
    text = notify.build_monthly(prev.year, prev.month, items)
    if send:
        send_report(text, month_data(prev.year, prev.month, items), name='monthly')
    else:
        print('[no-send]', text)
    state['_monthly'] = {'month': key, 'sent': riga.strftime('%Y-%m-%d %H:%M')}
    return True
