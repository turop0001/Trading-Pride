#!/usr/bin/env python3
"""Единый «тик» Пульта. ПЕРЕНЕСЕНО НА GITHUB ACTIONS 29.09.2026 (не зависит от Claude/сессии/
аккаунта) — запускается по cron каждые 5 минут в торговые окна (см. .github/workflows/tick.yml).
  10:00 — отчёт открытия окна A (build_window_open), далее каждые 5 мин проверка по полным правилам
          (pult_rules.analyze) — «Обновление» в Telegram только при изменении статуса, сигнал ВХОД;
  13:00 — отчёт закрытия окна A; 16:30 — открытие окна C; 18:30 — закрытие C; 19:00 — итог дня.
  Каждый тик обновляет данные Пульта (файлы state/pult_docs/*.json — читает Vercel-дашборд,
  раньше шло в db claude.ai-артефакта, теперь дашборд независим от Claude):
  строка «проверено в HH:MM — без изменений / изменилось: …» и карточки инструментов.
Состояние (state/pult_state.json) коммитится обратно в репозиторий в конце workflow — так оно
переживает между запусками, хотя каждый запуск GitHub Actions стартует с чистого контейнера.
Печатает в конце: NEXT_MIN: <минут до следующего тика> и ARTIFACT_DOCS: <список файлов>.
"""
import re
import sys, os, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_check as lc
from notify import (send_telegram, fmt_line, build_window_open, build_window_closed,
                    build_update, build_signal, build_daily_summary, build_weekly)

EVENTS = [(600, 'openA'), (780, 'closeA'), (990, 'openC'), (1110, 'closeC'), (1140, 'summary'), (1320, 'final')]
ALL_A = ['XAUUSD', 'EURUSD', 'GBPUSD', 'US500', 'NAS100', 'US30', 'GER40', 'AUDUSD', 'USDJPY', 'UK100', 'EURGBP']


def mins(t): return t.hour * 60 + t.minute


# 18.10.2026 (решение владельца): уведомления (Telegram, push) — только Тип C; Тип A считается и рисуется как раньше (карточки, state, аналитика), но не шлётся.
NOTIFY_WIN = ('C',)


def push(title, body, tag=None, sticky=False):
    """Push на телефон/компьютер (webpush_send.py); тихо ничего не делает, если ключа или подписок нет."""
    try:
        import webpush_send
        webpush_send.notify(title, body, tag, sticky)
    except Exception as e:
        print('push failed:', str(e)[:100])


def next_wake(riga, flags=None):
    m = mins(riga); wd = riga.weekday(); flags = flags or {}
    if wd < 5 and 600 <= m < 780:
        return max(1, 780 - m) if flags.get('allskipA') else 5
    if wd < 5 and 990 <= m < 1110:
        return max(1, 1110 - m) if flags.get('allskipC') else 5
    if wd < 5:
        for em, _ in EVENTS:
            if em > m: return max(1, em - m)
    # следующий будний день 10:00
    d = riga.date() + dt.timedelta(days=1)
    while d.weekday() >= 5: d += dt.timedelta(days=1)
    target = dt.datetime.combine(d, dt.time(10, 0))
    return max(1, int((target - riga.replace(second=0, microsecond=0)).total_seconds() // 60))


GER_PLACEHOLDER = {'sym': 'GER40', 'window': 'A', 'line_status': 'skip', 'direction': '—',
                   'note': 'СКИП (нет данных TradingView — смотреть вручную)', 'status_key': 'nodata',
                   'reasons': [], 'tg_note': 'СКИП'}


def syms_of(w):
    return syms(w)


def syms(w):
    return lc.WINDOW_SYMBOLS[w] + (['GER40'] if w == 'A' and 'GER40' not in lc.WINDOW_SYMBOLS[w] else [])


def ger40_result(state, today):
    """GER40 берётся из TradingView (ger40_tv.py пишет GER40_A_tv) — свежесть не старше 20 минут."""
    g = state.get('GER40_A_tv')
    if g and g.get('date') == today and dt.datetime.utcnow().timestamp() - g.get('fetched_utc', 0) <= 20 * 60:
        r = dict(g)
        g.pop('new_signal', None)   # сигнал отдаём один раз, повторные тики без нового фетча его не дублируют
        return r
    prev = state.get('GER40_A', {})
    if prev.get('date') == today and prev.get('source') == 'tv':
        return dict(prev)   # браузер временно недоступен — держим последний известный статус
    r = dict(GER_PLACEHOLDER); r['date'] = today
    return r


# ДОБАВЛЕНО 28.09.2026 (вечер): нарратив тренда H1(7д)/D1(14д) считается один раз в день на
# символ (не на каждый 5-минутный тик — незачем дёргать yfinance лишний раз) и кэшируется в
# state; используется в обоих окнах A/C для одного и того же символа.
def _trend_cached(state, sym, today):
    key = f'{sym}_trend'
    c = state.get(key, {})
    if c.get('date') == today and c.get('narr'):
        return c['narr']
    narr = lc.trend_narrative(lc.TICKERS.get(sym))
    state[key] = {'date': today, 'narr': narr}
    return narr


def analyze_window(state, window, today):
    res = {}
    for sym in lc.WINDOW_SYMBOLS[window]:
        key = f'{sym}_{window}'
        prev = state.get(key, {})
        if prev.get('date') != today: prev = {}
        try:
            r = lc.check_instrument(sym, lc.ticker_for(sym, window), window, prev)
        except Exception as e:
            r = {'sym': sym, 'error': str(e)}
        # временный сбой источника (stale) не считается изменением: держим последний настоящий статус
        if r.get('status_key') == 'stale' and prev and prev.get('status_key') != 'stale' and prev.get('line_status'):
            r = dict(prev)
        if r.get('error'):
            r = dict(prev) if prev else {'sym': sym, 'window': window, 'line_status': 'skip', 'direction': '—',
                                         'note': 'СКИП (нет данных у источника)', 'status_key': 'nodata'}
        r['date'] = today
        # 29.09.2026: скриншоты M5 и H1 в карточку — один раз, когда сделка закрылась (TP/SL)
        if prev.get('shots'):
            r['shots'] = prev['shots']
        elif r.get('signal') and any(x in (r.get('note') or '') for x in ('→ TP', '→ SL', '→ БУ')):
            try:   # 11.10.2026: запись для вкладки «Аналитика сделок» (последние 10 по A и C)
                import analytics_gen as _ag
                _ag.add_closed(sym, window, r, lc.riga_now()[1], today)
            except Exception as e:
                print('analytics failed:', sym, e)
            try:
                import shots as _sh
                sh = _sh.make_shots(sym, window, r, lc.riga_now()[1], today)
                if sh:
                    r['shots'] = sh
                    _hist_add(None, {'id': f"{today}_{sym}_{window}", 'date': today, 'symbol': sym, 'type': window,
                                     'result': r.get('note'), 'autopsy': r.get('autopsy'), 'sl_why': r.get('sl_why'), 'shots': sh})
            except Exception as e:
                print('shots failed:', sym, e)
        narr = _trend_cached(state, sym, today)
        if narr:
            r['trend_h1'] = narr.get('h1')
            r['trend_d1'] = narr.get('d1')
            # разбор стопа: добавляем «H1/D1 против входа», если тренд стал известен только сейчас
            try:
                if r.get('autopsy') and 'против входа' not in r['autopsy'] and r.get('signal'):
                    sd_ = 1 if r['signal'].get('side') == 'long' else -1
                    bad = [nm for k, nm in (('trend_h1', 'H1'), ('trend_d1', 'D1'))
                           if (sd_ == 1 and 'шорт' in str((r.get(k) or {}).get('tr', '')).lower())
                           or (sd_ == -1 and 'лонг' in str((r.get(k) or {}).get('tr', '')).lower())]
                    if bad:
                        r['autopsy'] += '; ' + ' и '.join(bad) + ' против входа'
                        _hist_add(None, {'id': f"{today}_{sym}_{window}", 'autopsy': r['autopsy']})
            except Exception as e:
                print('autopsy trend failed:', e)
        res[sym] = r
    # 29.09.2026: GER40 теперь считается по свечам MT5 (DE40 Tickmill); заглушка — только если их нет
    if window == 'A' and (res.get('GER40') or {}).get('status_key') in (None, 'nodata'):
        res['GER40'] = ger40_result(state, today)
    return res


# 28.09.2026 (по просьбе пользователя): в Telegram — только короткое слово статуса
# (tg_note), причины остаются в note/reasons только для карточек Пульта. closed=True
# (окно уже закрылось) сворачивает оставшиеся НАБЛЮДАЕМ/ВЫНОС без сделки в СКИП —
# "окно закрылось, входов не было = скип", как и попросил пользователь.
def _tg(r, closed=False):
    ls, note = r.get('line_status'), r.get('tg_note') or r.get('note', '')
    # 29.09.2026: в Telegram-группу подписчиков идут ТОЛЬКО статусы, без причин в скобках
    # (все причины видны в карточках Пульта). Смена одной лишь причины уведомления не даёт.
    note = re.sub(r'\s*\(.*\)\s*$', '', str(note or '')).strip()
    if closed and ls in ('watch', 'prep') and not r.get('signal'):
        return 'skip', 'СКИП'
    sg = r.get('signal') or {}
    if sg.get('time'):
        if note.startswith('ЗАКРЫТА'):
            if r.get('exit_time') and not note.endswith('22:00'): note += f" в {r['exit_time']}"
        elif note == 'ВХОД':
            note += f" в {sg['time']}"
    return ls, note


def lines_for(window, res, with_ger=True, closed=False):
    out = []
    for s in syms(window):
        r = res.get(s) or (GER_PLACEHOLDER if s == 'GER40' else None)
        if r:
            ls, note = _tg(r, closed)
            out.append(fmt_line(ls, s, r['direction'], note))
    return out


def result_of(res):
    n, pct = 0, 0.0
    for r in res.values():
        if r.get('signal'):
            n += 1
            rr = float((r.get('signal') or {}).get('rr') or 2)
            if 'TP' in r.get('note', ''): pct += rr
            elif 'SL' in r.get('note', ''): pct -= 1.0
            elif r.get('exit_r') is not None and 'закрыта в 22:00' in r.get('note', ''): pct += float(r['exit_r'])
    return n, pct


def _hist_add(state_dir_file, item):
    """ДОБАВЛЕНО 29.09.2026: архив карточек со статусом «Вход» для вкладки «История» (state/history.json)."""
    import json, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'history.json')
    try:
        items = json.load(open(path, encoding='utf-8'))
    except Exception:
        items = []
    i = next((k for k, x in enumerate(items) if x.get('id') == item['id']), None)
    if i is None: items.append(item)
    else: items[i] = {**items[i], **{k: v for k, v in item.items() if v is not None}}
    json.dump(items, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


EMO_TP, EMO_SL = '\U0001F7E2', '\U0001F534'


def final_check(state, today, dstr, off, tg, did, final=True):
    """22:00 Рига: сделки, которые на момент закрытия окна/отчёта дня были «В СДЕЛКЕ», проверяем
    один раз до конца дня. Если TP/SL уже случился — обновляем карточку, историю, скриншоты и
    шлём одно короткое сообщение с итогом сделки и обновлённым итогом дня."""
    upd = []
    chg = []
    for w in ('A', 'C'):
        for s in syms_of(w):
            r = state.get(f'{s}_{w}', {})
            if r.get('date') != today or not r.get('signal') or not str(r.get('note', '')).startswith('В СДЕЛКЕ'):
                continue
            sig = r['signal']
            try:
                d = lc.fetch(lc.ticker_for(s, w), sig.get('src', 'Yahoo'))
            except Exception as e:
                print('final fetch failed:', s, e); continue
            if d is None: continue
            long_ = sig.get('side') == 'long' or sig['tp'] > sig['entry']
            import pult_rules as _pr
            import pandas as _pd
            sd_ = 1 if long_ else -1
            tr = _pr._track({}, _pr._completed(d, dt.datetime.utcnow(), 5), sig, sd_, r.get('direction', ''), str)
            nt = str(tr.get('note', ''))
            if nt.startswith('В СДЕЛКЕ'): continue
            out = 'TP' if '→ TP' in nt else ('SL' if '→ SL' in nt else ('BE' if '→ БУ' in nt else 'T22'))
            if out == 'T22' and not final: continue
            r['note'] = nt
            r['tg_note'] = tr.get('tg_note') or ('ЗАКРЫТА - ' + out)
            if tr.get('exit_r') is not None: r['exit_r'] = tr['exit_r']
            if out == 'SL':
                r['autopsy'] = tr.get('autopsy') or _pr.autopsy(sig, sd_, d, r)
            for k_ in ('why', 'sl_why', 'prob'):
                if tr.get(k_) is not None: r[k_] = tr[k_]
            r['line_status'] = 'skip' if out == 'SL' else 'entry'
            r['status_key'] = r['note']
            try:   # 11.10.2026: финал дня — запись аналитики перезаписывается полным днём
                import analytics_gen as _ag
                _ag.add_closed(s, w, r, off, today, force=True)
            except Exception as e:
                print('final analytics failed:', s, e)
            try:
                import shots as _sh
                sh = _sh.make_shots(s, w, r, off, today)
                if sh: r['shots'] = sh
            except Exception as e:
                print('final shots failed:', s, e)
            try:
                _hist_add(None, {'id': f"{today}_{s}_{w}", 'result': r['note'], 'autopsy': r.get('autopsy'), 'sl_why': r.get('sl_why'), **({'shots': r['shots']} if r.get('shots') else {})})
            except Exception as e:
                print('final history failed:', e)
            state[f'{s}_{w}'] = r
            tm = tr.get('exit_time') or '22:00'
            r['exit_time'] = tm
            chg.append(1)
            if w not in NOTIFY_WIN: continue   # Тип A: карточки/state обновлены, уведомление не шлём
            rr_ = float(sig.get('rr') or 2)
            if out == 'T22':
                xr = float(r.get('exit_r') or 0)
                upd.append(f"\U0001F7E4 {s} ({r['direction']}) — закрыта в 22:00 "
                           f"({xr:+.1f}% депозита)")
            elif out == 'BE':
                upd.append(f"\U0001F7E4 {s} ({r['direction']}) — ЗАКРЫТА - БУ в {tm} (0% депозита)")
            else:
                upd.append(f"{EMO_TP if out == 'TP' else EMO_SL} {s} ({r['direction']}) — ЗАКРЫТА - {out} в {tm} "
                           f"({('+%.1f%%' % rr_) if out == 'TP' else '-1.0%'} депозита)")
    if upd:
        total = 0.0
        for w in NOTIFY_WIN:
            res = {s: state.get(f'{s}_{w}', {}) for s in syms_of(w) if state.get(f'{s}_{w}', {}).get('date') == today}
            total += result_of(res)[1]
        sign = '+' if total > 0 else ('-' if total < 0 else '')
        head = ("\U0001F4CA Итог сделок после отчёта дня · " + dstr + " (22:00 UTC+3)") if final else \
               ("\U0001F514 Обновление по сделкам · " + dstr + " (UTC+3)")
        for u_ in upd: push('Сделка закрыта', u_[:140])
        tg(head + "\n\n" + "\n".join(upd)
           + f"\n\n\U0001F3AF Итог дня: {sign}{abs(total):.1f}% депозита")
        ds = state.get('_daily_summary') or {}
        ds['total_pct'] = total; state['_daily_summary'] = ds
        did.append('final')
    return bool(upd) or bool(chg)


def _fix_uk100_20261021(state):
    """21.10.2026 (разовая правка, идемпотентная): UK100 Тип A за 21.10 ошибочно вошёл по неполным свечам (вынос 5.07 ATR),
    по свечам MT5 — СКИП (1.76 ATR < 1.93). Работающий цикл держит старое состояние в памяти и затирал исправление в ветке state,
    поэтому правим локальные файлы цикла: карточка, история, аналитика, скрины. Безопасно: любая ошибка игнорируется."""
    try:
        root = os.path.dirname(os.path.abspath(__file__)); sd = os.path.join(root, 'state')
        u = state.get('UK100_A') or {}
        if u.get('date') == '2026-10-21' and (u.get('signal') or {}).get('time') == '11:05':
            state['UK100_A'] = json.load(open(os.path.join(sd, '_fix_UK100_A_skip.json'), encoding='utf-8'))
        hp = os.path.join(sd, 'history.json')
        if os.path.exists(hp):
            h = json.load(open(hp, encoding='utf-8'))
            h2 = [x for x in h if x.get('id') != '2026-10-21_UK100_A']
            if len(h2) != len(h): json.dump(h2, open(hp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        ap = os.path.join(sd, 'analytics.json')
        if os.path.exists(ap):
            raw = open(ap, encoding='utf-8').read(); a = json.loads(raw)
            if any(r.get('id') == 'A_UK100_2026-10-21' for r in a.get('A', [])):
                g = json.load(open(os.path.join(sd, '_fix_A_GBPUSD_0908.json'), encoding='utf-8'))
                lst = [r for r in a['A'] if r.get('id') != 'A_UK100_2026-10-21']
                if not any(r.get('id') == g['id'] for r in lst): lst = [g] + lst
                a['A'] = lst[-10:]
                open(ap, 'w', encoding='utf-8').write(json.dumps(a, ensure_ascii=False, separators=(',', ':')) if '\n' not in raw.strip() else json.dumps(a, ensure_ascii=False, indent=1))
        for fn in ('2026-10-21_UK100_A_m5.png', '2026-10-21_UK100_A_h1.png'):
            p = os.path.join(sd, 'shots', fn)
            if os.path.exists(p): os.remove(p)
    except Exception as e:
        print('fix_uk100 failed:', e)


def _fix_c_20261021(state):
    """21.10.2026 (разовая правка, идемпотентная): EURUSD C (16:50) и UK100 C (17:00) задним числом превратились из СКИП (правило №8, встречный
    H1 FVG внутри цели 1:3) во ВХОД, когда цена дошла до цели и прошила FVG (инверсия/прошивка считалась по всей истории, а не до момента
    сигнала). Теперь _counter_fvg учитывает прошивку только до сигнала; здесь возвращаем карточки в СКИП, убираем сделки из истории и
    аналитики (+3R ×2 были ложными), удаляем скрины. Любая ошибка игнорируется."""
    try:
        root = os.path.dirname(os.path.abspath(__file__)); sd = os.path.join(root, 'state')
        bad = {'EURUSD_C': '16:50', 'UK100_C': '17:00'}
        sk = None
        for k, tm in bad.items():
            u = state.get(k) or {}
            if u.get('date') == '2026-10-21' and (u.get('signal') or {}).get('time') == tm:
                if sk is None: sk = json.load(open(os.path.join(sd, '_fix_C_skip.json'), encoding='utf-8'))
                state[k] = sk[k]
                try:
                    pdp = os.path.join(sd, 'pult_docs', f'pult__{k}.json')
                    if os.path.isdir(os.path.dirname(pdp)): json.dump(sk[k], open(pdp, 'w', encoding='utf-8'), ensure_ascii=False)
                except Exception as e:
                    print('fix_c doc failed:', e)
        ids = ('2026-10-21_EURUSD_C', '2026-10-21_UK100_C')
        hp = os.path.join(sd, 'history.json')
        if os.path.exists(hp):
            h = json.load(open(hp, encoding='utf-8'))
            h2 = [x for x in h if x.get('id') not in ids]
            if len(h2) != len(h): json.dump(h2, open(hp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        ap = os.path.join(sd, 'analytics.json')
        if os.path.exists(ap):
            raw = open(ap, encoding='utf-8').read(); a = json.loads(raw)
            aids = ('C_EURUSD_2026-10-21', 'C_UK100_2026-10-21')
            if any(r.get('id') in aids for r in a.get('C', [])):
                fill = json.load(open(os.path.join(sd, '_fix_C_fill.json'), encoding='utf-8'))
                lst = [r for r in a['C'] if r.get('id') not in aids]
                for g in reversed(fill):
                    if not any(r.get('id') == g['id'] for r in lst): lst = [g] + lst
                a['C'] = lst[-10:]
                open(ap, 'w', encoding='utf-8').write(json.dumps(a, ensure_ascii=False, separators=(',', ':')) if '\n' not in raw.strip() else json.dumps(a, ensure_ascii=False, indent=1))
        for sym in ('EURUSD', 'UK100'):
            for suf in ('m5', 'h1'):
                p = os.path.join(sd, 'shots', f'2026-10-21_{sym}_C_{suf}.png')
                if os.path.exists(p): os.remove(p)
    except Exception as e:
        print('fix_c failed:', e)


def _risk_pct_for(win):
    """21.10.2026: риск в сообщении сигнала. Стандарт 0,5% (решение владельца 18.10); у Типа C после 2 SL подряд по счёту
    (все инструменты вместе, БУ серию не меняет, TP сбрасывает) — 0,25% до первого TP. Серия берётся из state/history.json."""
    try:
        if win != 'C': return 0.5
        hp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'history.json')
        st = 0
        for x in json.load(open(hp, encoding='utf-8')):
            if x.get('type') != 'C': continue
            r = x.get('result') or ''
            if 'ВХОД →' not in r: continue
            if 'TP' in r: st = 0
            elif 'SL' in r: st += 1
        return 0.25 if st >= 2 else 0.5
    except Exception:
        return 0.5


def main(send=True):
    riga, off = lc.riga_now()
    today = riga.strftime('%Y-%m-%d'); dstr = riga.strftime('%d.%m.%Y'); t = riga.strftime('%H:%M')
    m = mins(riga); wd = riga.weekday()
    state = lc.load_state()
    _fix_uk100_20261021(state)
    _fix_c_20261021(state)
    flags = state.get('_flags', {})
    if flags.get('date') != today: flags = {'date': today}
    tg = (lambda x: send_telegram(x)) if send else (lambda x: print('[no-send]'))
    tgw = lambda w_, x: tg(x) if w_ in NOTIFY_WIN else print('[Тип', w_, 'без уведомления]')
    pushw = lambda w_, *a_, **k_: push(*a_, **k_) if w_ in NOTIFY_WIN else None
    window = lc.window_now(riga) if wd < 5 else None
    did = []

    # 20.10.2026 (решение владельца): MT5 выключен (нет свежих свечей советника) -> никаких сигналов, карточек и сообщений
    # в Telegram/push до его включения; окно открывается отчётом, когда свечи появятся. Yahoo как запасной путь отключён (live_check.MT5_ONLY).
    if wd < 5 and 600 <= m < 1320 and lc.MT5_ONLY and not lc.mt5_online():
        st_ = state.get('_mt5') or {}
        state['_mt5'] = {'online': False, 'since': st_.get('since') if st_.get('online') is False else t, 'date': today, 'checked': t}
        lc.save_state(state)
        print('MT5 OFFLINE - ждём включения советника, сигналов нет'); print('NEXT_MIN: 1')
        return
    if (state.get('_mt5') or {}).get('online') is False:
        state['_mt5'] = {'online': True, 'since': t, 'date': today}

    def check_and_update(win, first):
        res = analyze_window(state, win, today)
        changed, unchanged, syms, sigs = [], [], [], []
        for s, r in res.items():
            p = state.get(f'{s}_{win}', {})
            if p.get('date') != today: p = {}
            ls, tgnote = _tg(r)
            line = fmt_line(ls, s, r['direction'], tgnote)
            p_ls, p_tgnote = _tg(p)
            if (ls, r.get('direction'), tgnote) != (p_ls, p.get('direction'), p_tgnote):
                changed.append(line); syms.append(s)
                if not first and tgnote and not tgnote.startswith('НАБЛЮДАЕМ'):
                    pushw(win, f"{s} · тип {win} — {tgnote}", str(r.get('direction') or ''), tag=f'{s}_{win}')
            else:
                unchanged.append(line)
            if r.pop('new_signal', False): sigs.append(r)
            # 08.10.2026: цена дошла до уровня БУ (по формирующейся свече MT5) — один раз шлём «переноси стоп»
            if r.get('be_armed') and not p.get('be_armed') and str(r.get('note', '')).startswith('В СДЕЛКЕ') and (r.get('signal') or {}).get('be_at'):
                sg_ = r['signal']
                try:
                    tgw(win, f"\u26A0\uFE0F {s} ({r['direction']}) — цена прошла {round(100 * (sg_['be_at'] - sg_['entry']) / (sg_['tp'] - sg_['entry'])) if sg_.get('tp') != sg_.get('entry') else 80}% пути к цели (БУ {sg_['be_at']}). Переноси стоп на вход {sg_['entry']}.")
                    pushw(win, f"{s} · цена дошла до БУ", f"Переноси стоп на вход {sg_['entry']}", tag=f'{s}_{win}_be', sticky=True)
                    did.append('be_alert'); r['be_alert_at'] = t
                except Exception as e:
                    print('be alert failed:', e)
            elif p.get('be_alert_at') and r.get('be_armed'):
                r['be_alert_at'] = p['be_alert_at']
            state[f'{s}_{win}'] = r
        if first:
            nxt = ('C', '16:30') if (win == 'A' and lc.C_ENABLED) else (None, None)
            txt = build_window_open(dstr, win, '10:00–13:00' if win == 'A' else '16:30–18:30', lines_for(win, res), *nxt)
            if win == 'C': txt = txt + "\n\n⏰ Следующее — отчёт дня, 19:00."
            tgw(win, txt); did.append('open' + win); text = 'отчёт открытия окна отправлен'
        else:
            text = ('изменилось: ' + ', '.join(syms)) if syms else 'без изменений'
            if changed:
                tgw(win, build_update(dstr, win, t, changed, unchanged)); did.append('update')
        for r in sigs:
            sg = r['signal']
            try:
                _hist_add(None, {'id': f"{today}_{r['sym']}_{win}", 'date': today, 'symbol': r['sym'], 'type': win,
                                 'side': sg.get('side'), 'entry': sg.get('entry'), 'stop': sg.get('stop'), 'target': sg.get('tp'),
                                 'result': f"сигнал Пульта в {sg.get('time')}"})
            except Exception as e:
                print('history add failed:', e)
            tgw(win, build_signal(dstr, win, sg['time'], r['sym'], r['direction'], sg['entry'], sg['stop'], sg['tp'], _risk_pct_for(win),
                            note='по правилам Пульта — проверь график', rr=sg.get('rr') or 2)); did.append('signal')
        return text, syms, changed

    text, syms, changed_lines = None, [], []
    if window and not flags.get('allskip' + window):
        first = not flags.get('open' + window)
        text, syms, changed_lines = check_and_update(window, first)
        flags['open' + window] = True
        # все инструменты окна — СКИП (без временных сбоев данных) → проверки до закрытия окна не нужны
        cur = [state.get(f'{s}_{window}', {}) for s in syms_of(window)]
        if cur and all(c.get('line_status') == 'skip' and c.get('status_key') not in ('stale', 'nodata') and not c.get('signal') and c.get('note') != 'СКИП (нет данных у источника)' for c in cur):
            flags['allskip' + window] = True
            text = (text + '; ' if text and text != 'без изменений' else '') + 'все инструменты — СКИП, ждём закрытия окна'
    if wd < 5:
        for w, close_m, rng, nxt in (('A', 780, '10:00–13:00', ('C', '16:30') if lc.C_ENABLED else (None, None)), ('C', 1110, '16:30–18:30', (None, None))):
            if m >= close_m and flags.get('open' + w) and not flags.get('close' + w):
                # окно закрыто: НАБЛЮДАЕМ/ВЫНОС без сделки → СКИП (в state, чтобы карточки на сайте не висели)
                for s_ in syms_of(w):
                    c_ = state.get(f'{s_}_{w}', {})
                    if c_.get('date') == today and not c_.get('signal') and c_.get('line_status') in ('watch', 'prep'):
                        c_['line_status'] = 'skip'; c_['note'] = f'СКИП (вход не случился до {rng[-5:]})'
                        c_['tg_note'] = 'СКИП'; c_['ckf'] = []
                res = {s: state.get(f'{s}_{w}', {}) for s in syms_of(w) if state.get(f'{s}_{w}', {}).get('date') == today}
                n, pct = result_of(res)
                lines = lines_for(w, res, closed=True) if res else []
                txt = build_window_closed(dstr, w, rng, lines, nxt[0], nxt[1], trades=n, pct=pct, end_time=rng[-5:])
                if w == 'C': txt += "\n\n⏰ Следующее — отчёт дня, 19:00."
                if n and pct == 0: txt += "\n(результат сделки не закрыт на момент отчёта)"
                tgw(w, txt); flags['close' + w] = True; did.append('close' + w)
                text = text or f'окно {w} закрыто, отчёт отправлен'
        if m >= 1140 and not flags.get('summary') and (flags.get('openA') or flags.get('openC')):
            sections, total = [], 0.0
            for w in ('A', 'C'):
                res = {s: state.get(f'{s}_{w}', {}) for s in syms_of(w) if state.get(f'{s}_{w}', {}).get('date') == today}
                if not res: continue
                n, pct = result_of(res); total += pct
                # 28.09.2026: к 19:00 оба окна уже закрыты — остатки НАБЛЮДАЕМ/ВЫНОС без
                # сделки сворачиваем в СКИП (closed=True), отдельного раздела "Наблюдаем"
                # в итоговом отчёте дня больше нет (по просьбе пользователя).
                main_l = lines_for(w, res, closed=True)
                sections.append((w, main_l, []))
            sections_n = [x for x in sections if x[0] in NOTIFY_WIN]
            total_n = sum(result_of({s: state.get(f'{s}_{x[0]}', {}) for s in syms_of(x[0]) if state.get(f'{s}_{x[0]}', {}).get('date') == today})[1] for x in sections_n)
            tg(build_daily_summary(dstr, sections_n, total_n).replace('Отчёт дня · ' + dstr, 'Отчёт дня · ' + dstr + ' (тип C)', 1))
            flags['summary'] = True; did.append('summary'); text = text or 'отчёт дня отправлен'
            # ДОБАВЛЕНО 29.09.2026: сохраняем отчёт дня в state (коммитится в репозиторий вместе
            # с остальным state) — нужно странице Vercel, чтобы показывать тот же итог дня, что
            # ушёл в Telegram, без пересчёта.
            try:
                for w in ('A', 'C'):
                    for s_ in syms_of(w):
                        c = state.get(f'{s_}_{w}', {})
                        if c.get('date') == today and c.get('signal'):
                            _hist_add(None, {'id': f"{today}_{s_}_{w}", 'result': c.get('note'), 'autopsy': c.get('autopsy')})
            except Exception as e:
                print('history result failed:', e)
            state['_daily_summary'] = {'date': dstr, 'sections': [[w, l, wl] for w, l, wl in sections], 'total_pct': total}

    # ДОБАВЛЕНО 29.09.2026: сделки, оставшиеся открытыми после закрытия своего окна (A → в окне C),
    # проверяем каждые 5 минут, чтобы SL/TP появлялся в карточке и Telegram сразу, а не в 22:00.
    if wd < 5 and 600 <= m < 1320:
        try:
            if final_check(state, today, dstr, off, tg, did, final=False):
                text = text or 'закрыта сделка окна A — карточка обновлена'
        except Exception as e:
            print('sweep failed:', e)

    if wd < 5 and m >= 1320 and not flags.get('final') and (flags.get('openA') or flags.get('openC')):
        flags['final'] = True
        if final_check(state, today, dstr, off, tg, did):
            text = text or 'итог сделок после отчёта дня отправлен'

    # ДОБАВЛЕНО 06.10.2026 (утверждено пользователем): недельный отчёт в Telegram — пятница 22:00 Рига, после итога сделок дня.
    # TP/SL, WR, итог в R и в % депозита (риск 1% на сделку), отдельно Тип A и Тип C. Данные — state/history.json.
    try:
        # 10.10.2026: запас на случай пропуска GitHub-расписания в 22:00 (09.10 за час не было ни одного запуска): недельный отчёт
        # догоняется в сб/вс и в пн до 12:00 Рига, если за прошедшую неделю он ещё не отправлен
        _wk_due = (wd == 4 and m >= 1320) or wd in (5, 6) or (wd == 0 and m < 720)
        if _wk_due:
            mon_ = riga.date() - dt.timedelta(days=(wd if wd != 0 else 7))
            fri_ = mon_ + dt.timedelta(days=4)
            if (state.get('_weekly') or {}).get('week') != str(mon_):
                hp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'history.json')
                try: items_ = json.load(open(hp, encoding='utf-8'))
                except Exception: items_ = []
                if send:   # 08.10.2026: картинка + текст ОДНИМ сообщением (при сбое картинки — обычный текст, как раньше)
                    import report_image as _ri
                    _wtxt = build_weekly(mon_, fri_, items_)   # 10.10.2026: в подписи только заголовок (две строки), остальное — на картинке; при сбое картинки уйдёт полный текст
                    _ri.send_report(_wtxt, _ri.week_data(mon_, fri_, items_), 'weekly', caption='\n'.join(_wtxt.split('\n')[:2]))
                else:
                    print('[no-send]')
                state['_weekly'] = {'week': str(mon_), 'sent': t}
                did.append('weekly'); text = text or 'недельный отчёт отправлен'
    except Exception as e:
        print('weekly report failed:', e)

    # ДОБАВЛЕНО 08.10.2026: итоги месяца — 1-го числа (с 10:00 Рига; если 1-е выпало на выходной — в первый будний запуск до 3-го).
    # Картинка + текст одним сообщением; флаг state['_monthly']. В выходные 1-го числа отправляет monthly.yml.
    try:
        if m >= 600:
            import report_image as _ri
            hp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'history.json')
            try: items_m = json.load(open(hp, encoding='utf-8'))
            except Exception: items_m = []
            if _ri.maybe_send_monthly(state, riga, items_m, send=send):
                did.append('monthly'); text = text or 'итоги месяца отправлены'
    except Exception as e:
        print('monthly report failed:', e)

    try:
        import news as _news; _news.refresh(state, today)
    except Exception as e:
        print('news hook failed:', e)
    state['_flags'] = flags
    if text:
        log = state.get('_log', [])
        if log and log[-1].get('date') != today: log = []
        log.append({'date': today, 'time': t, 'window': window or '—', 'text': text, 'lines': changed_lines})
        state['_log'] = log[-80:]
    lc.save_state(state)
    docs = []
    if window or did:
        docs = lc.build_artifact_payload(state, riga, window or ('C' if m >= 990 else 'A'), syms, text or 'без изменений')
    print('DONE:', t, did, text)
    print('ARTIFACT_DOCS:', json.dumps([f"{x['collection']}__{x['doc_id']}.json" for x in docs]))
    print('NEXT_MIN:', next_wake(riga, flags))


if __name__ == '__main__':
    # 29.09.2026: если минутный цикл (pult_loop.py) жив — 5-минутный запуск ничего не делает
    try:
        import time as _t
        if '--force' not in sys.argv and _t.time() - int(open('state/loop_heartbeat.txt').read()) < 180:
            print('loop alive — skip'); sys.exit(0)
    except (OSError, ValueError):
        pass
    main(send='--no-send' not in sys.argv)
