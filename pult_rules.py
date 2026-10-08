#!/usr/bin/env python3
"""Полный механический разбор инструмента по правилам Пульта для ЖИВЫХ проверок.

v76 (28.09.2026, ПЕРВЫЙ в истории проекта прямой бэктест 2024-2026 самой функции
analyze() — не упрощённой копии scan.py/nyscan3.py — по всем инструментам, шаг
проверки 30 мин, см. «трейдинг/решение-фильтры-v76.md»):
  - Убраны фильтры: аномальная свеча в боксе, инверсия своего H1 FVG, встречный
    H1 FVG внутри бокса, встречный H4 FVG с реакцией, вынос сформировал встречный
    H1 FVG.
  - РЕАЛЬНЫЙ итог по факту (2024-2026, без GER40 — для него нет истории для
    бэктеста): Тип A 719 сделок / 59,1% / +556R, Тип C 130 сделок / 60,8% / +107R.
    Старые цифры 890/68,9%/+949R и 384/65,6%/+372R были НЕВЕРНЫ — их считал
    scan.py/nyscan3.py, упрощённая копия правил, которая (помимо отсутствия
    фильтров 2-5,8) требует только 1 сильную свечу выкупа вместо 2-х и не
    проверяет инверсию встречного m5 FVG — то есть она мягче боевого кода
    по двум дополнительным пунктам, не только по фильтрам FVG.
  - СТОП = хай/лоу ТОЛЬКО последней подтверждающей свечи выноса (v75), для обоих типов.
  - Для Типа A нет блокирующего фильтра встречного H1 FVG до цели; для Типа C он тоже
    отключён (не менялось).

v77 (28.09.2026, перенос Типа C на nyscan3-логику по решению пользователя, честно
проверено ПРИЧИННЫМ тик-харнессом — не ретроспективой — 2024-2026, все инструменты):
  - Тип A НЕ МЕНЯЛСЯ: проверено 9 альтернативных вариантов входа/выкупа/стопа (перенос
    scan.py-формулы, стабилизация экстремума, 2-я сильная свеча вместо 1-й, разные
    откаты/буферы стопа) — ни один не дал лучше 719/+556R/DD-7R ни по доходу, ни по
    просадке, текущая логика — локальный оптимум. Осталась без изменений.
  - Тип C ЗАМЕНЁН: bias теперь РЕАКТИВНЫЙ (пробой закрытием верх/низ сегодняшнего
    лондонского бокса В САМОМ ОКНЕ ВХОДА задаёт направление напрямую, при пробое ОБЕИХ
    сторон побеждает более поздний по времени пробой) — а не сравнение с лондонским
    боксом ВЧЕРАШНЕГО дня, как было и как остаётся для Типа A. Выкуп теперь через
    engulf-проверку (закрытие свечи пробивает open последней встречной свечи перед
    экстремумом, ищем среди 4 свечей назад от экстремума) вместо инверсии встречного m5
    FVG; сильных свечей нужно ≥2 (не изменилось), стоп по-прежнему за хаем/лоем ТОЛЬКО
    последней свечи выноса (v75, без изменений), блокирующий фильтр встречного H1 FVG
    до цели 1:2 — снят (его и раньше не было для Типа C). ЧЕСТНЫЙ ИТОГ по факту
    (2024-2026, причинный тик-тест): n=501, WR 58,5%, +378R, просадка -7R, серия SL 7 —
    против 130/60,8%/+107R/DD-5R/серия5 на старой логике. Просадка/серия SL немного
    выросли, но доход почти утроился — компромисс одобрен пользователем.

Что проверяется (всё, что можно посчитать по OHLC без визуального графика):
  1. bias: Тип A — сегодняшний бокс vs вчерашний (LONG/SHORT/скип-внутри/скип-обхват);
     Тип C — реактивный, задаётся пробоем в самом окне входа (см. v77 выше).
  2. Тип A: противоположная сторона бокса снята (закрытием) первой → скип на весь день;
     Тип C: при пробое обеих сторон бокса направление задаёт более поздний пробой
     (без скипа — это и есть суть реактивного bias, см. v77).
  3. вынос нужной стороны подтверждается ЗАКРЫТИЕМ 5m свечи за границей.
  4. выкуп: Тип A — возврат в бокс/откат ≥30%, сильные свечи (тело ≥60%), встречный m5
     FVG в выносных свечах инвертирован телом, нет выкупа за 24 бара (2ч) → скип; Тип C —
     engulf-свеча пробивает закрытием open встречной свечи перед экстремумом (см. v77),
     сильных свечей ≥2.
  5. вход: открытие свечи после ПЕРВОЙ сильной свечи выкупа, когда сильных ≥2;
     стоп за хаем/лоем последней подтверждающей свечи выноса − 0.05·ATR; цель 2R.
  6. после входа — отслеживание TP/SL по барам.
НЕ проверяется механически (остаётся визуальной частью отчётов 10:00/16:30): реальная
ликвидность слева/цель уже собрана, компрессия ликвидности, тренд 5 дней, CHoCH, гэпы, новости.
"""
import datetime as dt
import re
import numpy as np
import pandas as pd

BOX = {'A': (180, 600), 'C': (660, 985)}      # минуты Риги: Азия 03:00-10:00, Лондон 11:00-16:25
WIN = {'A': (600, 840), 'C': (990, 1110)}     # окна входа 10:00-14:00, 16:30-18:30
DEC = {'XAUUSD': 2, 'EURUSD': 5, 'GBPUSD': 5, 'US500': 1, 'NAS100': 1, 'US30': 0, 'GER40': 1}


def prev_trading_date(d):
    p = d - dt.timedelta(days=1)
    while p.weekday() >= 5:
        p -= dt.timedelta(days=1)
    return p


def _completed(df, now_utc, minutes):
    """Оставляем только ЗАКРЫТЫЕ бары (последний бар yfinance часто ещё формируется)."""
    # 30.09.2026: запас 40 с после закрытия бара — на границе (тик в :01) источник (MT5-мост) ещё отдаёт
    # незавершённый бар: в 10:05 цена 4195,03 «закрылась» выше бокса (СКИП), в 10:06 итоговое закрытие 4193,90.
    end = df.index + pd.Timedelta(minutes=minutes)
    return df[end <= pd.Timestamp(now_utc, tz='UTC') - pd.Timedelta(seconds=40)]


def _resample(d, rule, offset=None):
    kw = {'offset': offset} if offset else {}
    r = d[['Open', 'High', 'Low', 'Close']].resample(rule, label='left', closed='left', **kw).agg(
        {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    return r


def _fvgs(F, min_size):
    H, L, C, T = F['High'].values, F['Low'].values, F['Close'].values, F.index
    out = []
    for k in range(1, len(F) - 1):
        if H[k - 1] < L[k + 1] and (L[k + 1] - H[k - 1]) >= min_size:
            out.append(dict(k=k, t=T[k], lo=float(H[k - 1]), hi=float(L[k + 1]), dir=1))
        if L[k - 1] > H[k + 1] and (L[k - 1] - H[k + 1]) >= min_size:
            out.append(dict(k=k, t=T[k], lo=float(H[k + 1]), hi=float(L[k - 1]), dir=-1))
    for f in out:
        f['inv_t'] = None; f['touch_t'] = None; f['reject'] = False
        for j in range(f['k'] + 2, len(F)):
            if f['dir'] == 1:
                if f['touch_t'] is None and L[j] <= f['hi']: f['touch_t'] = T[j]
                if C[j] < f['lo']: f['inv_t'] = T[j]; break
                if f['touch_t'] is not None and C[j] > f['hi']: f['reject'] = True
            else:
                if f['touch_t'] is None and H[j] >= f['lo']: f['touch_t'] = T[j]
                if C[j] > f['hi']: f['inv_t'] = T[j]; break
                if f['touch_t'] is not None and C[j] < f['lo']: f['reject'] = True
    return out


def fvg_ctx(sd, d, now_utc, off, extreme, price, box_a, box_b, sweep_t0, fmtp, tp=None, days=10, typ='A'):
    """ИНФО-пометки по FVG H1/H4 (окно `days` суток, только неинвертированные). Вход НЕ блокируют.
    Возвращает список dict(n=номер пункта чек-листа, on=bool, t=текст)."""
    out = []
    try:
        offh = '1h' if off == 3 else '2h'
        H1 = _completed(_resample(d, '1h'), now_utc, 60)
        H4 = _completed(_resample(d, '4h', offh), now_utc, 240)
        if len(H1) < 20 or len(H4) < 6:
            return out
        atr1 = float((H1['High'] - H1['Low']).iloc[-14:].mean())
        atr4 = float((H4['High'] - H4['Low']).iloc[-14:].mean())
        F1 = _fvgs(H1.iloc[-days * 24:], 0.15 * atr1)
        F4 = _fvgs(H4.iloc[-days * 6:], 0.15 * atr4)
        rng = lambda f: f'{fmtp(f["lo"])}–{fmtp(f["hi"])}'
        A_ = (lambda n, on, t: out.append(dict(n=n, on=bool(on), t=t)))
        # батут по направлению: неинвертированный FVG в нашу сторону, экстремум выноса внутри/рядом
        if extreme is not None:
            b = []
            for nm, F, at in (('H1', F1, atr1), ('H4', F4, atr4)):
                for f in F:
                    if f['dir'] == sd and f['inv_t'] is None and f['lo'] - 0.2 * at <= extreme <= f['hi'] + 0.2 * at:
                        b.append(f'{nm} {rng(f)}')
                        break
            A_(0, b, ('справка: батут ' + ', '.join(b)) if b else 'справка: батута под выносом нет')
        # встречные на пути
        _pre = []
        for nm, F, n_ in (('H1', F1, 21), ('H4', F4, 21)):
            cand = [f for f in F if f['dir'] == -sd and f['inv_t'] is None and ((f['lo'] > price) if sd == 1 else (f['hi'] < price))]
            if cand:
                f = min(cand, key=lambda z: z['lo']) if sd == 1 else max(cand, key=lambda z: z['hi'])
                lvl = f['lo'] if sd == 1 else f['hi']
                pre = ''
                if tp is not None:
                    pre = ', до цели 2R' if ((lvl < tp) if sd == 1 else (lvl > tp)) else ', за целью 2R'
                _pre.append(pre)
                A_(n_, True, f'встречный {nm} {rng(f)}{pre}')
        # УСИЛИТЕЛЬ (тест Dukascopy 2024–26: Тип A 71% против 53%, Тип C 74% против 51%): встречный FVG есть, но ЗА целью 2R, между входом и целью — нет
        if tp is not None:
            _far = bool(_pre) and all(x == ', за целью 2R' for x in _pre)
            A_(24, _far, 'встречный FVG за целью 2R, до цели чисто (усилитель)' if _far else 'встречного FVG за целью 2R (при чистом пути) нет')
        # H4 встречный с реакцией (касание + отскок)
        r4 = [f for f in F4 if f['dir'] == -sd and f['inv_t'] is None and f['reject']]
        if r4:
            A_(15, True, f'H4 встречный с реакцией {rng(r4[-1])}')
        # встречный H1, образованный внутри бокса (Азия / Лондон)
        if box_a is not None:
            ia = [f for f in F1 if f['dir'] == -sd and f['inv_t'] is None and box_a <= f['t'] < box_b]
            A_(18, ia, ('встречный H1 внутри бокса ' + rng(ia[-1])) if ia else 'встречного H1 внутри бокса нет')
        # встречный H1, образованный выносом
        if sweep_t0 is not None:
            t0 = sweep_t0.floor('1h') - pd.Timedelta(hours=1)
            sw = [f for f in F1 if f['dir'] == -sd and f['inv_t'] is None and f['t'] >= t0]
            A_(14, sw, ('вынос образовал встречный H1 ' + rng(sw[-1])) if sw else 'вынос встречного H1 не образовал')
    except Exception:
        pass
    if typ == 'C':
        mp = {15: 11, 24: 12}
        out = [dict(x, n=mp.get(x['n'], 0)) for x in out]
    return out


def _strong(o, h, l, c, sd):
    rng = h - l
    return (c - o) * sd > 0 and rng > 0 and abs(c - o) / rng >= 0.6


def _box(d, date, a, b):
    m = d[(d['rdate'] == date) & (d['rmin'] >= a) & (d['rmin'] < b)]
    return m


def _analyze_C(sym, d, now_utc, off, prev):
    dec = DEC.get(sym, 5)
    fmtp = lambda x: f"{x:.{dec}f}"
    window = 'C'
    if len(d) < 50:
        return dict(error='no_data')
    loc = d.index + pd.Timedelta(hours=off)
    d['rdate'] = [x.date() for x in loc]
    d['rmin'] = [x.hour * 60 + x.minute for x in loc]
    today = (now_utc + dt.timedelta(hours=off)).date()
    ba, bb = BOX[window]
    wa, wb = WIN[window]

    box = _box(d, today, ba, bb)
    if len(box) < 10:
        return dict(error='no_box')
    boxH, boxL = float(box['High'].max()), float(box['Low'].min())
    price = float(d['Close'].iloc[-1])
    res = dict(sym=sym, window=window, price=round(price, dec), boxH=round(boxH, dec), boxL=round(boxL, dec),
               reasons=[], checked_at=(now_utc + dt.timedelta(hours=off)).strftime('%H:%M'), ck=[1], ckf=[])
    # ck/ckf — номера пунктов чек-листа Типа C (нумерация вкладки «Чек-лист»)

    if prev.get('signal') and prev['signal'].get('date') == str(today) and prev['signal'].get('window') == window:
        sd0 = 1 if prev['signal']['side'] == 'long' else -1
        dirc0 = '▲ LONG' if sd0 == 1 else '🔻 SHORT'
        return _track(res, d, prev['signal'], sd0, dirc0, fmtp)

    rng5 = (d['High'] - d['Low'])
    atr5 = float(rng5.iloc[-14:].mean())

    Dtoday = d[d['rdate'] == today].sort_index()
    if len(Dtoday) < 5:
        return _out(res, 'watch', '—', 'НАБЛЮДАЕМ')
    AO, AH, AL, AC = Dtoday['Open'].values, Dtoday['High'].values, Dtoday['Low'].values, Dtoday['Close'].values
    Arm = Dtoday['rmin'].values
    win_idx = [i for i in range(len(Dtoday)) if wa <= Arm[i] < wb]
    if not win_idx:
        return _out(res, 'watch', '—', 'НАБЛЮДАЕМ')

    up = [i for i in win_idx if AC[i] > boxH]
    dn = [i for i in win_idx if AC[i] < boxL]
    if not up and not dn:
        return _out(res, 'watch', '—', 'НАБЛЮДАЕМ')
    if up and dn:
        if up[-1] > dn[-1]:
            ext, sd = up[-1], -1
        else:
            ext, sd = dn[-1], 1
    elif up:
        ext, sd = up[-1], -1
    else:
        ext, sd = dn[-1], 1
    bias = 'long' if sd == 1 else 'short'
    dirc = '▲ LONG' if sd == 1 else '🔻 SHORT'
    res['ck'] = [1, 2] + ([3] if (up and dn) else [])

    extreme = float(AL[ext] if sd == 1 else AH[ext])
    res['extreme'] = round(extreme, dec)
    sweep_t = (Dtoday.index[ext] + pd.Timedelta(hours=off)).strftime('%H:%M')
    _bs = pd.Timestamp(dt.datetime.combine(today, dt.time(0, 0)) + dt.timedelta(minutes=ba) - dt.timedelta(hours=off), tz='UTC')
    _be = _bs + dt.timedelta(minutes=bb - ba)
    _sw = Dtoday.index[(dn if sd == 1 else up)[0]]
    res['fx'] = fvg_ctx(sd, d, now_utc, off, extreme, price, _bs, _be, _sw, fmtp, typ='C')

    # opp: до 1 свечи ПРОТИВ направления сделки, ищем от ext назад (вкл.) на 4 свечи —
    # может залезать за начало окна входа (в конец лондонского бокса), как в nyscan3.
    opp = []
    for j in range(ext, max(ext - 4, 0) - 1, -1):
        if (AC[j] - AO[j]) * sd < 0:
            opp.append(j)
    opp = opp[:1]  # nopp=1

    sig = None
    if opp:
        try:
            _mo = max(AO[j] for j in opp) if sd == 1 else min(AO[j] for j in opp)
            if any(i > ext and (AC[i] - _mo) * sd > 0 and (AC[i] - AO[i]) * sd > 0 for i in win_idx):
                res['ck'] = sorted(set(res['ck'] + [4]))
            if len([j for j in range(ext + 1, len(AO)) if _strong(AO[j], AH[j], AL[j], AC[j], sd)]) >= 2:
                res['ck'] = sorted(set(res['ck'] + [5]))
        except Exception:
            pass
        for i in win_idx:
            if i <= ext:
                continue
            eng = (AC[i] - (max(AO[j] for j in opp) if sd == 1 else min(AO[j] for j in opp))) * sd > 0
            if not eng:
                continue
            if (AC[i] - AO[i]) * sd <= 0:
                continue
            st = [j for j in range(ext + 1, i + 1) if _strong(AO[j], AH[j], AL[j], AC[j], sd)]
            if len(st) < 2:
                continue
            je = st[0] + 1
            if je >= len(Dtoday) or je <= ext:
                continue
            entry = float(AO[je])
            stop = extreme - sd * 0.05 * atr5
            R = abs(entry - stop)
            if R <= 0:
                continue
            tp = entry + sd * 2 * R
            sig = dict(date=str(today), window=window,
                       time=(Dtoday.index[je] + pd.Timedelta(hours=off)).strftime('%H:%M'),
                       t_utc=str(Dtoday.index[je]), entry=round(entry, dec), stop=round(stop, dec),
                       tp=round(tp, dec), side=bias)
            res['ck'] = sorted(set(res['ck'] + [4, 5, 6, 7, 8]))
            sig['ck'] = list(res['ck'])
            res['fx'] = fvg_ctx(sd, d, now_utc, off, extreme, price, _bs, _be, _sw, fmtp, tp=tp, typ='C')
            sig['fx'] = res['fx']
            break

    if sig:
        res['signal'] = sig
        res['new_signal'] = True
        return _out(res, 'entry', dirc, f'ВХОД ({sig["time"]}, {fmtp(sig["entry"])})')
    way = 'вниз' if sd == -1 else 'вверх'
    n_st = len([j for j in range(ext + 1, len(AO)) if _strong(AO[j], AH[j], AL[j], AC[j], sd)])
    if not opp:
        return _out(res, 'prep', dirc, f'ВЫНОС (в {sweep_t}, ждём откат и сильную свечу {way})')
    if n_st == 0:
        return _out(res, 'prep', dirc, f'ВЫНОС (в {sweep_t}, ждём две сильные свечи {way})')
    if n_st == 1:
        return _out(res, 'prep', dirc, f'ВЫНОС (в {sweep_t}, ждём вторую сильную свечу {way})')
    return _out(res, 'prep', dirc, f'ВЫНОС (в {sweep_t}, ждём свечу-поглощение {way})')


_AMP_NAMES = {'A': {13: 'батут (H1 FVG)', 14: 'ликвидность на пути', 15: 'по тренду'}, 'C': {11: 'батут (H1 FVG)', 12: 'тренд не против'}}


def finalize_why(res):
    """«Все причины» по итогу (02.10.2026): скип — только причина скипа; в сделке — основание входа;
    TP — коротко; SL — разбор стопа (структура против, нет усилителей, ликвидность за стопом, затяжной боковик)."""
    if not isinstance(res, dict) or res.get('error'): return res
    sig = res.get('signal') or {}
    st, note, why = res.get('line_status'), str(res.get('note') or ''), list(res.get('why') or [])
    if not sig:
        if st == 'skip':
            sk = [w for w in why if w.startswith('Скип')]
            if sk: res['why'] = sk
        return res
    win = sig.get('window') or 'A'
    names = _AMP_NAMES.get(win, _AMP_NAMES['A'])
    pl = [names[n] for n in (sig.get('plus') or []) if n in names]
    wr = sig.get('worse') or []
    side = 'LONG' if sig.get('side') in ('long', 'LONG') else 'SHORT'
    rec, conf = sig.get('struct'), sig.get('sconf')
    cf = f', {conf}' if conf else ''
    if rec == side: stx = f'структура {rec}{cf}: по тренду'
    elif rec and rec != '50/50': stx = f'структура {rec}{cf}: вход против структуры'
    else: stx = 'структура без преимущества'
    amp = ('усилители: ' + ', '.join(pl)) if pl else 'усилителей не было'
    if wr: amp += '; ухудшитель №' + _nums(wr)
    inn = f'вход {sig.get("time", "")} по {sig.get("entry", "")}, вероятность {sig.get("prob", "—")}; {amp}; {stx}'
    xt = res.get('exit_time') or ''
    if '→ TP' in note:
        res['why'] = [f'Цель {sig.get("rr", 2):g}R достигнута{(" в " + xt) if xt else ""}: {inn}.']
        res.pop('sl_why', None)
    elif '→ SL' in note:
        miss = []
        if rec and rec not in (side, '50/50'): miss.append(f'вход против структуры (рекомендация {rec}{cf})')
        if not pl: miss.append('усилителей не было')
        if wr: miss.append('был ухудшитель №' + _nums(wr) + ' (ликвидность у стороны выноса)')
        if sig.get('prob') in ('низкая', 'средняя'): miss.append(f'вероятность была {sig.get("prob")}')
        lx = sig.get('liqx')
        if lx: miss.append(f'неснятая ликвидность {lx["name"]} {lx["p"]} всего в {lx["dR"]:.1f}R за стопом — цена пошла её снимать')
        if (sig.get('swn') or 0) > 20: miss.append(f'затяжной боковик после выноса: {sig["swn"]} свечей до триггера')
        txt = f'Стоп{(" в " + xt) if xt else ""} (вход {sig.get("time", "")} по {sig.get("entry", "")}). Причины: ' + ('; '.join(miss) if miss else 'все условия были выполнены — стоп в рамках статистики') + '.'
        if res.get('autopsy'): txt += ' Ход сделки: ' + str(res['autopsy']).rstrip('.') + '.'
        res['why'] = [txt]; res.pop('sl_why', None)
    elif '→ БУ' in note:
        res['why'] = [f'Закрыта в безубыток после достижения уровня БУ: {inn}.']
        res.pop('sl_why', None)
    elif 'закрыта в 22:00' in note:
        res['why'] = [f'Закрыта по времени в 22:00 ({note.split("(")[-1].rstrip(")")}): {inn}.']
        res.pop('sl_why', None)
    else:
        res['why'] = [f'В сделке: {inn}.']
    return res



LEGACY_A = False   # True — старая логика Типа A (v77, 2R); с 01.10.2026 по умолчанию S1


def analyze(sym, d, window, now_utc, off, prev=None, h1=None):
    """d — 5m OHLC (UTC index) за ~10 дней. prev — прошлое состояние инструмента (для сигнала/TP/SL).
    h1 — часовые бары (UTC, ~40 суток) для цепочки H1 (Тип A, S1). Возвращает dict со статусом в формате Пульта."""
    prev = prev or {}
    if window == 'C':
        return finalize_why(_analyze_C2(sym, d, now_utc, off, prev, h1))
    if window == 'A' and not LEGACY_A:
        return finalize_why(_analyze_A_s1(sym, d, now_utc, off, prev, h1))
    dec = DEC.get(sym, 5)
    fmtp = lambda x: f"{x:.{dec}f}"
    d = _completed(d, now_utc, 5).copy()
    if len(d) < 50:
        return dict(error='no_data')
    loc = d.index + pd.Timedelta(hours=off)
    d['rdate'] = [x.date() for x in loc]
    d['rmin'] = [x.hour * 60 + x.minute for x in loc]
    today = (now_utc + dt.timedelta(hours=off)).date()
    ba, bb = BOX[window]
    wa, wb = WIN[window]

    box = _box(d, today, ba, bb)
    pbox = _box(d, prev_trading_date(today), ba, bb)
    if len(box) < 10:
        return dict(error='no_box')
    boxH, boxL = float(box['High'].max()), float(box['Low'].min())
    price = float(d['Close'].iloc[-1])
    res = dict(sym=sym, window=window, price=round(price, dec), boxH=round(boxH, dec), boxL=round(boxL, dec),
               reasons=[], checked_at=(now_utc + dt.timedelta(hours=off)).strftime('%H:%M'), ck=[1], ckf=[])
    # ck/ckf — номера пунктов чек-листа Типа A (нумерация вкладки «Чек-лист»: обязательные → скип-условия → усилители → ½ риска)

    # 1. bias
    bias = None
    if len(pbox) >= 10:
        pH, pL = float(pbox['High'].max()), float(pbox['Low'].min())
        res['prevH'], res['prevL'] = round(pH, dec), round(pL, dec)
        if boxH > pH and boxL < pL: bias = 'skip_envelope'
        elif boxH <= pH and boxL >= pL: bias = 'skip_inside'
        elif boxH > pH: bias = 'long'
        elif boxL < pL: bias = 'short'
    res['bias'] = bias
    if bias == 'skip_envelope':
        res['ckf'] = [2]
        return _out(res, 'skip', '—', 'СКИП (бокс шире вчерашнего с обеих сторон)')
    if bias == 'skip_inside':
        res['ckf'] = [2]
        return _out(res, 'skip', '—', 'СКИП (внутренний день)')
    if bias is None:
        return _out(res, 'watch', '—', 'НАБЛЮДАЕМ (нет данных за вчера)')
    sd = 1 if bias == 'long' else -1
    res['ck'] = [1, 2, 4]
    dirc = '▲ LONG' if sd == 1 else '🔻 SHORT'
    dirb = dirc  # ИСПРАВЛЕНО 29.09.2026: слово "bias" убрано из текста везде
    side_word = 'лонговый' if sd == 1 else 'шортовый'
    opp_word = 'шортовый' if sd == 1 else 'лонговый'

    # если сигнал уже был — ведём сделку (TP/SL), правила входа больше не пересчитываем
    if prev.get('signal') and prev['signal'].get('date') == str(today) and prev['signal'].get('window') == window:
        return _track(res, d, prev['signal'], sd, dirc, fmtp)

    # ATR
    rng5 = (d['High'] - d['Low'])
    atr5 = float(rng5.iloc[-14:].mean())
    offset_h = '1h' if off == 3 else '2h'
    H1 = _completed(_resample(d, '1h'), now_utc, 60)
    H4 = _completed(_resample(d, '4h', offset_h), now_utc, 240)
    atr1 = float((H1['High'] - H1['Low']).iloc[-14:].mean()) if len(H1) >= 14 else atr5 * 3
    atr4 = float((H4['High'] - H4['Low']).iloc[-14:].mean()) if len(H4) >= 14 else atr1 * 2
    f1 = _fvgs(H1.iloc[-5 * 24:], 0.15 * atr1)   # 5 суток назад, как в боевом коде v73
    f4 = _fvgs(H4, 0.15 * atr4)
    box_start_utc = pd.Timestamp(dt.datetime.combine(today, dt.time(ba // 60, ba % 60)) - dt.timedelta(hours=off), tz='UTC')
    win_start_utc = pd.Timestamp(dt.datetime.combine(today, dt.time(wa // 60, wa % 60)) - dt.timedelta(hours=off), tz='UTC')
    day_ago = pd.Timestamp(now_utc, tz='UTC') - pd.Timedelta(hours=24)

    skips = []

    # окно
    W = d[(d['rdate'] == today) & (d['rmin'] >= wa) & (d['rmin'] < wb)]
    O, Hh, Ll, C = W['Open'].values, W['High'].values, W['Low'].values, W['Close'].values
    up = [i for i in range(len(W)) if C[i] > boxH]
    dn = [i for i in range(len(W)) if C[i] < boxL]
    need, other = (dn, up) if sd == 1 else (up, dn)
    # 2. противоположная сторона снята первой
    if other and (not need or other[0] < need[0]):
        skips.append('противоположная сторона бокса снята первой')
    else:
        # вынос ТЕНЬЮ противоположной стороны раньше нашего выноса — тоже снятие (тест 2024–26: WR 17–21% vs 40–44%)
        _ow = [i for i in range(len(W)) if (Hh[i] > boxH if sd == 1 else Ll[i] < boxL)]
        if _ow and (not need or _ow[0] < need[0]):
            skips.append('противоположная сторона бокса снята тенью первой')

    _bs = pd.Timestamp(dt.datetime.combine(today, dt.time(0, 0)) + dt.timedelta(minutes=ba) - dt.timedelta(hours=off), tz='UTC')
    _be = _bs + dt.timedelta(minutes=bb - ba)
    _ex = float(Ll[need[-1]] if sd == 1 else Hh[need[-1]]) if need else None
    _sw = W.index[need[0]] if need else None
    res['fx'] = fvg_ctx(sd, d, now_utc, off, _ex, price, _bs, _be, _sw, fmtp)
    if skips:
        res['ckf'] = [5]
        short = [re.sub(r'\s*\([^)]*\d[^)]*\)', '', x) for x in skips[:2]]
        return _out(res, 'skip', dirb, f'СКИП ({"; ".join(short)})', skips)
    res['ck'] = [1, 2, 4, 5]
    if not need:
        return _out(res, 'watch', dirb, 'НАБЛЮДАЕМ')
    res['ck'] = [1, 2, 3, 4, 5]

    # 3. вынос подтверждён закрытием
    ext = need[-1]
    # v75 (28.09.2026): стоп = хай/лоу ТОЛЬКО последней подтверждающей свечи (ext),
    # а не истинный экстремум всего сегмента выноса (было в v73/v74) — решение
    # принято по бэктесту 2024-2026, см. «трейдинг/решение-стоп-v75.md».
    extreme = float(Ll[ext] if sd == 1 else Hh[ext])
    res['extreme'] = round(extreme, dec)
    sweep_t = (W.index[need[0]] + pd.Timedelta(hours=off)).strftime('%H:%M')

    # 4. выкуп
    after = list(range(ext + 1, len(W)))
    if len(after) > 24:
        st_all = [j for j in after[:24] if _strong(O[j], Hh[j], Ll[j], C[j], sd)]
        if len(st_all) < 2:
            res['ckf'] = [9]
            return _out(res, 'skip', dirb, 'СКИП (выкуп не сформировался за 2 часа)')
    st = [j for j in after if _strong(O[j], Hh[j], Ll[j], C[j], sd)]
    edge = boxL if sd == 1 else boxH
    back = any(((C[j] >= edge) if sd == 1 else (C[j] <= edge)) or
               abs(C[j] - extreme) >= 0.3 * abs(edge - extreme) for j in after)
    if back: res['ck'] = sorted(set(res['ck'] + [6]))
    if len(st) >= 2: res['ck'] = sorted(set(res['ck'] + [8]))

    # m5 встречный FVG в выносных свечах (последние 5 до ext) должен быть инвертирован телом
    lo5 = max(0, need[0] - 4)
    m5_block = None
    for k in range(lo5 + 1, ext + 1):
        if k + 1 >= len(W): break
        if sd == 1 and Ll[k - 1] > Hh[k + 1]:
            zlo, zhi = Hh[k + 1], Ll[k - 1]
            if not any(C[j] > zhi for j in range(k + 2, len(W))): m5_block = (zlo, zhi)
        if sd == -1 and Hh[k - 1] < Ll[k + 1]:
            zlo, zhi = Hh[k - 1], Ll[k + 1]
            if not any(C[j] < zlo for j in range(k + 2, len(W))): m5_block = (zlo, zhi)

    if not st:
        return _out(res, 'prep', dirc, f'ВЫНОС ({"лоя" if sd == 1 else "хая"} в {sweep_t}, ждём выкуп)')
    if len(st) < 2 or not back:
        return _out(res, 'prep', dirc, 'ВЫНОС (выкуп 1 сильная свеча, ждём вторую)')
    if m5_block:
        return _out(res, 'prep', dirc, 'ВЫНОС (ждём инверсию встречного m5 FVG)')
    res['ck'] = sorted(set(res['ck'] + [10]))

    # 5. вход
    je = st[0] + 1
    if je >= len(W):
        return _out(res, 'prep', dirc, 'ВЫНОС (выкуп подтверждён, ждём свечу входа)')
    entry = float(O[je])
    stop = extreme - sd * 0.05 * atr5
    R = abs(entry - stop)
    if R <= 0:
        return _out(res, 'skip', dirb, 'СКИП (некорректный стоп)')
    tp = entry + sd * 2 * R
    # блок цели 1:2 (встречный H1 FVG без реакции) — v75: только для Типа C.
    # Для Типа A снят по бэктесту 2024-2026 (без него n=890, R=+949, DD=-5R против
    # n=285, R=+297, DD=-5R с ним — см. «трейдинг/решение-стоп-v75.md»).
    if window == 'C':
        react = any(f['dir'] == sd and f['inv_t'] is None and extreme <= f['hi'] and extreme >= f['lo'] - atr1 * 0.2 for f in f1)
        if not react:
            for f in f1:
                if f['dir'] == -sd and f['inv_t'] is None:
                    if sd == 1 and f['lo'] > entry and f['lo'] < tp and (f['lo'] - entry) < 1.9 * R:
                        return _out(res, 'skip', dirb, f'СКИП (встречный H1 FVG до цели 1:2, {fmtp(f["lo"])})')
                    if sd == -1 and f['hi'] < entry and f['hi'] > tp and (entry - f['hi']) < 1.9 * R:
                        return _out(res, 'skip', dirb, f'СКИП (встречный H1 FVG до цели 1:2, {fmtp(f["hi"])})')
    res['ck'] = sorted(set(res['ck'] + [7]))
    sig = dict(date=str(today), window=window, time=(W.index[je] + pd.Timedelta(hours=off)).strftime('%H:%M'),
               t_utc=str(W.index[je]), entry=round(entry, dec), stop=round(stop, dec), tp=round(tp, dec), side=bias,
               ck=list(res['ck']))
    res['fx'] = fvg_ctx(sd, d, now_utc, off, extreme, price, _bs, _be, _sw, fmtp, tp=tp)
    sig['fx'] = res['fx']
    res['signal'] = sig
    res['new_signal'] = True
    return _out(res, 'entry', dirc, f'ВХОД ({sig["time"]}, {fmtp(entry)})')


def _h1_fvgs(h1c):
    atr1 = float((h1c['High'] - h1c['Low']).iloc[-14:].mean())
    return _fvgs(h1c.iloc[-240:], 0.15 * atr1), atr1


def _counter_fvg(F1, sd, entry, tp):
    """Встречный неинвертированный H1 FVG внутри пути entry → tp (1:2)."""
    for f in F1:
        if f['dir'] != -sd or f['inv_t'] is not None: continue
        if sd == 1 and f['hi'] > entry and f['lo'] <= tp: return f
        if sd == -1 and f['lo'] < entry and f['hi'] >= tp: return f
    return None


def _hdr(res, d, h1, now_utc, off, today, price, boxH, boxL, fm, end_m):
    """Структура Swing/Sub, ликвидность, позиция цены относительно бокса (общее для типов A и C)."""
    import pult_ctx as X
    ctx = X.build(d, h1, now_utc, off, today, price, _completed, lambda x: _resample(x, '1h'))
    liq = X.liquidity(ctx['h1c'], d, today, off, price)
    sw, sb = ctx['swing'], ctx['sub']
    res['struct'] = dict(swing=f"{X._arrow(sw['tr'])} {sw['txt']}" + (f" ({sw['brk']})" if sw.get('brk') else ''),
                         sub=f"{X._arrow(sb['tr'])} {sb['txt']}", rec=ctx['rec'], conf=ctx['conf'], score=ctx['score'],
                         line=X.struct_line(ctx, price, liq, fm))
    res['pos'] = X.box_pos(d, today, price, boxH, boxL, end_m)
    return ctx, liq


def _nums(nn):
    return ', '.join(str(n) for n in sorted(set(nn)))


def _why(res, txt, nn=None):
    res.setdefault('why', []).append(txt + (f' (№{_nums(nn)})' if nn else ''))


def _amps_A(res, ctx, liq, sd, boxH, boxL, win_start_utc):
    """Усилители/ухудшитель Типа A: 11 батут, 12 ликвидность на пути (≤30% длины Азии), 13 по тренду; 14 ухудшитель."""
    rngA = max(boxH - boxL, 1e-12)
    F1, _ = _h1_fvgs(ctx['h1c'])
    plus, worse, notes = [], [], []
    for f in F1:
        if f['dir'] != sd or f['inv_t'] is not None or f['t'] >= win_start_utc: continue
        if f['touch_t'] is not None and f['touch_t'] < win_start_utc: continue
        if sd == 1 and f['hi'] <= boxL and boxL - f['hi'] <= 0.5 * rngA: plus.append(13); notes.append(f'батут: нетронутый H1 FVG под лоем Азии ({f["lo"]:.5g}–{f["hi"]:.5g})'); break
        if sd == -1 and f['lo'] >= boxH and f['lo'] - boxH <= 0.5 * rngA: plus.append(13); notes.append(f'батут: нетронутый H1 FVG над хаем Азии ({f["lo"]:.5g}–{f["hi"]:.5g})'); break
    if sd == 1:
        path = [x for x in liq if x['kind'] == 'hi' and 0 < x['p'] - boxH <= 0.3 * rngA]
        sidew = [x for x in liq if x['kind'] == 'lo' and 0 < boxL - x['p'] <= 0.3 * rngA]
    else:
        path = [x for x in liq if x['kind'] == 'lo' and 0 < boxL - x['p'] <= 0.3 * rngA]
        sidew = [x for x in liq if x['kind'] == 'hi' and 0 < x['p'] - boxH <= 0.3 * rngA]
    if path: plus.append(14); notes.append(f'ликвидность на пути в пределах 30% Азии: {path[0]["name"]} {path[0]["p"]:.5g}')
    if ctx['rec'] == ('LONG' if sd == 1 else 'SHORT'): plus.append(15); notes.append('сторона по тренду (структура Swing+Sub)')
    if sidew: worse.append(16); notes.append(f'ухудшитель: несобранная ликвидность у стороны выноса в пределах 30% Азии: {sidew[0]["name"]} {sidew[0]["p"]:.5g}')
    return plus, worse, notes, F1


def _prob_set(res, plus, worse, typ='A'):
    import pult_ctx as X
    res['plus'] = list(plus); res['worse'] = list(worse)
    if typ == 'A': res['prob'] = X.prob_word(len(plus), len(worse))
    else: res['prob'] = 'высокая' if len(plus) >= 2 else 'средняя' if len(plus) == 1 else 'низкая'


def _analyze_A_s1(sym, d, now_utc, off, prev, h1):
    """Тип A (S1, правка 01.10.2026): без цепочки H1, цель 2R, встречный H1 FVG внутри 1:2 = СКИП,
    усилители (батут, ликвидность на пути ≤30% Азии, по тренду) и ухудшитель (ликвидность у стороны выноса).
    Нумерация пунктов — вкладка «Чек-лист» Типа A: основные 1–9 (№3 — противоположная сторона бокса Азии не снята раньше нужного выноса; №5 — вынос ≥0,5 ATR M5, с 07.10.2026; №6 — V-разворот ≤7 значимых свечей), условия входа 10–12, усилители 13–15, ухудшитель 16."""
    import pult_s1 as S1
    dec = DEC.get(sym, 5)
    fmtp = lambda x: f"{x:.{dec}f}"
    d = _completed(d, now_utc, 5).copy()
    if len(d) < 50:
        return dict(error='no_data')
    loc = d.index + pd.Timedelta(hours=off)
    d['rdate'] = [x.date() for x in loc]
    d['rmin'] = [x.hour * 60 + x.minute for x in loc]
    today = (now_utc + dt.timedelta(hours=off)).date()
    nowm = (now_utc + dt.timedelta(hours=off)).hour * 60 + (now_utc + dt.timedelta(hours=off)).minute
    ba, bb = BOX['A']
    box = _box(d, today, ba, bb)
    pbox = _box(d, prev_trading_date(today), ba, bb)
    if len(box) < 10:
        return dict(error='no_box')
    boxH, boxL = float(box['High'].max()), float(box['Low'].min())
    price = float(d['Close'].iloc[-1])
    res = dict(sym=sym, window='A', price=round(price, dec), boxH=round(boxH, dec), boxL=round(boxL, dec),
               reasons=[], checked_at=(now_utc + dt.timedelta(hours=off)).strftime('%H:%M'), ck=[1], ckf=[], why=[], ckv=3)
    ctx, liq = _hdr(res, d, h1, now_utc, off, today, price, boxH, boxL, fmtp, bb)
    bias = None
    if len(pbox) >= 10:
        pH, pL = float(pbox['High'].max()), float(pbox['Low'].min())
        res['prevH'], res['prevL'] = round(pH, dec), round(pL, dec)
        if boxH > pH and boxL < pL: bias = 'skip_envelope'
        elif boxH <= pH and boxL >= pL: bias = 'skip_inside'
        elif boxH > pH: bias = 'long'
        elif boxL < pL: bias = 'short'
    res['bias'] = bias
    if bias in ('skip_envelope', 'skip_inside'):
        res['ckf'] = [2]
        t = 'бокс Азии шире вчерашнего с обеих сторон' if bias == 'skip_envelope' else 'Азия внутри вчерашней (внутренний день)'
        res['reasons'] = [t]; _why(res, 'Скип: ' + t, [2])
        return _out(res, 'skip', '—', 'СКИП (' + ('бокс шире вчерашнего с обеих сторон' if bias == 'skip_envelope' else 'внутренний день') + ')')
    if bias is None:
        _why(res, 'Нет данных за вчера')
        return _out(res, 'watch', '—', 'НАБЛЮДАЕМ (нет данных за вчера)')
    sd = 1 if bias == 'long' else -1
    res['ck'] = [1, 2]
    dirc = '▲ LONG' if sd == 1 else '🔻 SHORT'
    _why(res, ('Азия выше вчерашней по хаю — только лонг' if sd == 1 else 'Азия ниже вчерашней по лою — только шорт'), [2])
    win_start = pd.Timestamp(dt.datetime.combine(today, dt.time(10, 0)) - dt.timedelta(hours=off), tz='UTC')
    plus, worse, notes, F1 = _amps_A(res, ctx, liq, sd, boxH, boxL, win_start)
    _prob_set(res, plus, worse)
    for n_t in notes: _why(res, n_t)
    res['ck'] = sorted(set(res['ck'] + plus))

    # сделка уже есть — только ведём (TP 2R / SL / закрытие в 22:00)
    if prev.get('signal') and prev['signal'].get('date') == str(today) and prev['signal'].get('window') == 'A':
        _sg = prev['signal']
        _v = _sg.get('ckv') or 1
        if _v < 3:   # сигнал записан старой нумерацией: v1 (до 06.10, 1–14), v2 (06.10, 1–15) → v3 (с 07.10, 1–16)
            _mv = lambda nn: [(lambda x: x + 1 if x >= 5 else x)(n + 1 if (_v < 2 and n >= 3) else n) for n in (nn or [])]
            _sg['ck'] = _mv(_sg.get('ck')); _sg['plus'] = _mv(_sg.get('plus')); _sg['worse'] = _mv(_sg.get('worse')); _sg['ckv'] = 3
        _pw = prev['signal'].get('why')
        if not _pw:
            _pw = [f'Вынос {"лоя" if sd == 1 else "хая"} Азии, V-разворот, M5 FVG и триггер выполнены — вход в {prev["signal"].get("time", "")} (пункты ' + _nums(prev['signal'].get('ck') or []) + ')']
        res['why'] = list(_pw) + [w for w in (res.get('why') or []) if w not in _pw]
        r_ = _track(res, d, prev['signal'], sd, dirc, fmtp)
        return _close_why(r_)

    # №3 (06.10.2026, обязательный): противоположная сторона бокса Азии (хай для лонга, лой для шорта) не снята раньше нужного выноса —
    # ни тенью, ни телом, в окне 10:00–14:00. Если снята первой — СКИП дня по инструменту (тест 5 лет: 161 сделка отсеяна, WR 40%).
    _wi = np.flatnonzero((d['rdate'].values == today) & (d['rmin'].values >= 600) & (d['rmin'].values < 840))
    _need = _oth = None
    for _g in _wi:
        _hn = (d['Low'].values[_g] < boxL) if sd == 1 else (d['High'].values[_g] > boxH)
        _ho = (d['High'].values[_g] > boxH) if sd == 1 else (d['Low'].values[_g] < boxL)
        if _hn and _need is None: _need = _g
        if _ho and _oth is None: _oth = _g
        if _need is not None or _oth is not None: break
    if _oth is not None and (_need is None or _oth < _need):
        _t_oth = (d.index[_oth] + pd.Timedelta(hours=off)).strftime('%H:%M')
        t = f'противоположная сторона бокса Азии ({"хай" if sd == 1 else "лой"}) снята раньше нужного выноса в {_t_oth}'
        res['ckf'] = [3]; res['reasons'] = [t]; _why(res, 'Скип: ' + t, [3])
        return _out(res, 'skip', dirc, f'СКИП (противоположная сторона Азии снята первой в {_t_oth})')
    res['ck'] = sorted(set(res['ck'] + [3]))
    r = S1.analyze_day(d, today, off, sd, h1)
    if r['start'] is None:
        if nowm >= 840:
            res['ckf'] = [10]; res['reasons'] = ['вынос не случился до 14:00']; _why(res, 'Скип: вынос не случился до 14:00', [10])
            return _out(res, 'skip', dirc, 'СКИП (вынос не случился до 14:00)')
        return _out(res, 'watch', dirc, 'НАБЛЮДАЕМ')
    sweep_t = (d.index[r['start']] + pd.Timedelta(hours=off)).strftime('%H:%M')
    res['ck'] = sorted(set(res['ck'] + [4]))
    _why(res, f'Вынос {"лоя" if sd == 1 else "хая"} Азии в {sweep_t}', [4])
    c = r['cand']
    if c is None:
        res['extreme'] = round(sd * (r['last_ext_f'] if r.get('last_ext_f') is not None else 0), dec)
        _sa = r.get('last_sw_atr')
        if _sa is not None:
            if _sa >= S1.MINSW:
                res['ck'] = sorted(set(res['ck'] + [5])); _why(res, f'Вынос {_sa:.2f} ATR — не меньше {S1.MINSW:g} ATR', [5])
            else:
                _why(res, f'Вынос пока {_sa:.2f} ATR — меньше {S1.MINSW:g} ATR: откат от такого выноса — шум, ждём углубления', [5])
        if nowm >= 840:
            res['ckf'] = [10]; res['reasons'] = ['вход не случился до 14:00']; _why(res, 'Скип: условия входа не выполнены до 14:00', [10])
            return _out(res, 'skip', dirc, 'СКИП (вход не случился до 14:00)')
        return _out(res, 'prep', dirc, f'ВЫНОС ({"лоя" if sd == 1 else "хая"} в {sweep_t}, ждём вход)')
    g = c['g']
    ext = sd * c['ext_f']
    res['extreme'] = round(ext, dec)
    res['ck'] = sorted(set(res['ck'] + [5, 6, 7, 8]))
    _why(res, f'Вынос {c.get("sw_atr", 0):.2f} ATR (≥{S1.MINSW:g}), V-разворот: {c.get("nbars", 0)} значимых свечей (≤{S1.VBARS}), M5 FVG перекрыт, триггер входа ({"≥2 сильных свечи (вынос ≤1,5 ATR)" if c.get("sw_atr", 0) <= S1.SWTRG else "≥3 сильных или откат ≥30% (вынос больше 1,5 ATR)"})', [5, 6, 7, 8])
    if g + 1 >= len(d):
        # предварительная проверка №11 по текущей цене (вход будет по открытию следующей свечи): не ждём лишнюю минуту
        e0 = float(d['Close'].iloc[-1]); s0 = ext - sd * S1.BUF * c['atr']; R0 = (e0 - s0) * sd
        if R0 > 0:
            cf0 = _counter_fvg(F1, sd, e0, e0 + sd * S1.RR * R0)
            if cf0 is not None:
                res['ckf'] = [11]; res['ck'] = sorted(set(res['ck'] + [9, 10, 12]))   # пройдены все, кроме №11
                t = f'встречный H1 FVG {fmtp(cf0["lo"])}–{fmtp(cf0["hi"])} внутри цели 1:2 (по текущей цене {fmtp(e0)})'
                res['reasons'] = [t]; _why(res, 'Скип: ' + t, [11])
                return _out(res, 'skip', dirc, 'СКИП (встречный H1 FVG внутри цели 1:2)')
        return _out(res, 'prep', dirc, 'ВЫНОС (условия входа выполнены, ждём свечу входа)')
    entry = float(d['Open'].iloc[g + 1])
    stop = ext - sd * S1.BUF * c['atr']
    R = abs(entry - stop)
    if (entry - stop) * sd <= 0 or R <= 0:
        return _out(res, 'skip', dirc, 'СКИП (некорректный стоп)')
    tp = entry + sd * S1.RR * R
    cf = _counter_fvg(F1, sd, entry, tp)
    if cf is not None:
        res['ckf'] = [11]; res['ck'] = sorted(set(res['ck'] + [9, 10, 12]))
        t = f'встречный H1 FVG {fmtp(cf["lo"])}–{fmtp(cf["hi"])} внутри цели 1:2'
        res['reasons'] = [t]; _why(res, 'Скип: ' + t, [11])
        return _out(res, 'skip', dirc, 'СКИП (встречный H1 FVG внутри цели 1:2)')
    t_in = d.index[g + 1]
    end_utc = pd.Timestamp(dt.datetime.combine(today, dt.time(S1.END_M // 60, S1.END_M % 60)) - dt.timedelta(hours=off), tz='UTC')
    res['ck'] = sorted(set(res['ck'] + [9, 10, 11, 12]))
    liqx = None   # 02.10.2026: ближайшая неснятая ликвидность стороны выноса ЗА стопом (для разбора SL)
    try:
        cl = [x for x in liq if x['kind'] == ('lo' if sd == 1 else 'hi') and (x['p'] - stop) * sd < 0]
        if cl:
            x_ = max(cl, key=lambda z: z['p']) if sd == 1 else min(cl, key=lambda z: z['p'])
            dR = abs(x_['p'] - stop) / R
            if dR <= 1.5: liqx = dict(name=x_['name'], p=round(x_['p'], dec), dR=round(dR, 2))
    except Exception:
        liqx = None
    swn = int(g - r['start'] + 1)   # свечей от начала выноса до триггера
    sig = dict(date=str(today), window='A', time=(t_in + pd.Timedelta(hours=off)).strftime('%H:%M'),
               t_utc=str(t_in), entry=round(entry, dec), stop=round(stop, dec), tp=round(tp, dec), side=bias,
               rr=S1.RR, end_utc=str(end_utc), ck=list(res['ck']), plus=list(plus), worse=list(worse), prob=res['prob'],
               strong=int(c['strong']), struct=res['struct']['rec'], sconf=res['struct'].get('conf'), sscore=res['struct'].get('score'),
               liqx=liqx, swn=swn, ckv=3)
    res['signal'] = sig
    res['new_signal'] = True
    _why(res, f'ВХОД: вероятность закрытия цели {res["prob"]}; выполнены пункты ' + _nums(res['ck']))
    sig['why'] = list(res.get('why') or [])
    return _out(res, 'entry', dirc, f'ВХОД ({sig["time"]}, {fmtp(entry)})')


def _close_why(res):
    """Причины и анализ ошибок при закрытии сделки (TP / SL / БУ / 22:00): что учтено, что нет."""
    sig = res.get('signal') or {}
    tg = res.get('tg_note') or ''
    if not tg.startswith('ЗАКРЫТА') or not sig: return res
    ck, pl, wr = sig.get('ck') or [], sig.get('plus') or [], sig.get('worse') or []
    base = f'вероятность была {sig.get("prob", "—")}; выполнено: ' + _nums(ck)
    if wr: base += '; ухудшитель №' + _nums(wr)
    res.setdefault('why', []).append(f'{tg.replace("ЗАКРЫТА - ", "Итог ")}: {base}')
    if 'SL' in tg:
        miss = []
        amps_all = [13, 14, 15] if sig.get('window') == 'A' else [11, 12]
        no_amp = [n for n in amps_all if n not in pl]
        if wr: miss.append(f'не избежали ухудшителя №{_nums(wr)}')
        if no_amp: miss.append(f'не было усилителей №{_nums(no_amp)}')
        rec = sig.get('struct')
        side = 'LONG' if sig.get('side') in ('long', 'LONG') else 'SHORT'
        if rec and rec not in (side, '50/50'): miss.append(f'структура рекомендовала {rec} — вход был против')
        res['sl_why'] = ('Разбор SL: ' + ('; '.join(miss) if miss else 'все пункты и усилители были выполнены — стоп в рамках статистики (WR ~78%)') + '.')
        if res.get('autopsy'): res['sl_why'] += ' ' + res['autopsy']
    return res


def _analyze_C2(sym, d, now_utc, off, prev, h1):
    """Тип C (новые правила 01.10.2026). Бокс Лондона 11:00–16:25, вход 16:30–18:30. Вынос телом или тенью:
    вниз → лонг, вверх → шорт (вчерашний Лондон не важен). ≤4 свечей выноса (доджи не считаются), широкий M5 FVG
    (≥2× средней свечи Лондона) в 3 свечах перед экстремумом — СКИП; вход ВСЕГДА на откате 20% длины выноса
    (с 08.10.2026; поглощение свечи выноса отменено), стоп за экстремумом +0,1R, цель 3R, БУ на 50% пути, встречный H1 FVG внутри 1:3 — СКИП.
    Нумерация: основные 1–6, скипы 7–10, усилители 11–12."""
    dec = DEC.get(sym, 5)
    fmtp = lambda x: f"{x:.{dec}f}"
    d = _completed(d, now_utc, 5).copy()
    if len(d) < 50:
        return dict(error='no_data')
    loc = d.index + pd.Timedelta(hours=off)
    d['rdate'] = [x.date() for x in loc]
    d['rmin'] = [x.hour * 60 + x.minute for x in loc]
    today = (now_utc + dt.timedelta(hours=off)).date()
    nl = now_utc + dt.timedelta(hours=off)
    nowm = nl.hour * 60 + nl.minute
    ba, bb = BOX['C']; wa, wb = WIN['C']
    box = _box(d, today, ba, bb)
    if len(box) < 10:
        return dict(error='no_box')
    boxH, boxL = float(box['High'].max()), float(box['Low'].min())
    price = float(d['Close'].iloc[-1])
    res = dict(sym=sym, window='C', price=round(price, dec), boxH=round(boxH, dec), boxL=round(boxL, dec),
               reasons=[], checked_at=nl.strftime('%H:%M'), ck=[1, 2], ckf=[], why=[])
    ctx, liq = _hdr(res, d, h1, now_utc, off, today, price, boxH, boxL, fmtp, bb)
    if nowm < bb and not (prev.get('signal') and prev['signal'].get('date') == str(today)):
        res['ck'] = [1]
        _why(res, 'Бокс Лондона ещё формируется (до 16:25)')
        return _out(res, 'watch', '—', 'НАБЛЮДАЕМ (бокс Лондона формируется)')
    if prev.get('signal') and prev['signal'].get('date') == str(today) and prev['signal'].get('window') == 'C':
        sg = prev['signal']
        sd = 1 if sg.get('side') == 'long' else -1
        dirc = '▲ LONG' if sd == 1 else '🔻 SHORT'
        if sg.get('sv') != 2:
            # 02.10.2026: сигналы, выданные до исправления структуры Swing (ложный «слом вверх»), пересчитываем по
            # структуре НА МОМЕНТ ВХОДА: сторона против структуры → по структуре даёт усилитель №12, меняется вероятность
            try:
                import pult_ctx as _X
                cut = pd.Timestamp(sg['t_utc']) + pd.Timedelta(minutes=5)
                cut_n = cut.tz_convert('UTC').tz_localize(None).to_pydatetime() if cut.tzinfo else cut.to_pydatetime()
                c0 = _X.build(d[d.index < cut], h1, cut_n, off, today, float(sg['entry']), _completed, lambda x: _resample(x, '1h'))
                pl = [x for x in (sg.get('plus') or []) if x != 12]
                if c0['rec'] == ('LONG' if sd == 1 else 'SHORT'): pl.append(12)
                sg['plus'] = sorted(pl); sg['struct'] = c0['rec']; sg['sconf'] = c0['conf']; sg['sscore'] = c0['score']
                sg['prob'] = 'высокая' if len(pl) >= 2 else 'средняя' if len(pl) == 1 else 'низкая'
                if 12 in pl: sg['ck'] = sorted(set((sg.get('ck') or []) + [12]))
                else: sg['ck'] = [x for x in (sg.get('ck') or []) if x != 12]
                sg['sv'] = 2
            except Exception as e:
                print('struct fix failed', sym, e)
        _prob_set(res, sg.get('plus') or [], [], 'C')
        return _close_why(_track(res, d, sg, sd, dirc, fmtp))
    day = d[d['rdate'] == today]
    win = day[(day['rmin'] >= wa) & (day['rmin'] < 1320)]
    idx = {t: i for i, t in enumerate(d.index)}
    # направление — по первому выносу границы бокса (тело или тень)
    sd = None; g0 = None
    for t, r in win.iterrows():
        dn = r['Low'] < boxL; up = r['High'] > boxH
        if dn or up:
            if dn and up: sd = 1 if r['Close'] < r['Open'] else -1
            else: sd = 1 if dn else -1
            g0 = idx[t]; break
    if sd is None:
        _why(res, 'Бокс Лондона 11:00–16:25 сформирован; выноса границы пока нет', [2])
        if nowm >= 1110:
            res['ckf'] = [3]; res['reasons'] = ['вынос не случился до 18:30']; _why(res, 'Скип: вынос не случился до 18:30', [3])
            return _out(res, 'skip', '—', 'СКИП (вынос не случился до 18:30)')
        return _out(res, 'watch', '—', 'НАБЛЮДАЕМ')
    dirc = '▲ LONG' if sd == 1 else '🔻 SHORT'
    O0, H0, L0, C0 = [d[c].values.astype(float) for c in ('Open', 'High', 'Low', 'Close')]
    if sd == 1: O, H, L, C = O0, H0, L0, C0; lowB = boxL
    else: O, H, L, C = -O0, -L0, -H0, -C0; lowB = -boxH
    n = len(d)
    # усилители C: 10 батут (H1 FVG, от которого пошёл выкуп), 11 тренд / боковик
    F1, atr1 = _h1_fvgs(ctx['h1c'])
    plus = []
    if ctx['rec'] == ('LONG' if sd == 1 else 'SHORT'): plus.append(12)
    ext = L[g0]; ge = g0
    res['ck'] = sorted(set(res['ck'] + [3]))
    _why(res, f'Вынос {"лоя" if sd == 1 else "хая"} лондонского бокса в {(d.index[g0] + pd.Timedelta(hours=off)).strftime("%H:%M")} → {"лонг" if sd == 1 else "шорт"}', [3])
    lim = min(n, idx.get(win.index[-1], n - 1) + 1) if len(win) else n
    def _nsw(a_, b_):
        k = 0
        for q in range(a_, b_ + 1):
            rg = H[q] - L[q]
            if not (rg > 0 and abs(C[q] - O[q]) <= 0.25 * rg): k += 1
        return k
    entry_g = None; mode = 'pb20'
    for g in range(g0, n):
        if d['rdate'].iloc[g] != today: continue
        if L[g] < ext:
            ext = L[g]; ge = g; continue
        if g == g0: continue
        leg = lowB - ext
        if leg <= 0: continue
        lvl = ext + 0.2 * leg
        if g <= ge: continue
        # 08.10.2026: вход ВСЕГДА на откате 20% длины выноса (вход по поглощению свечи выноса отменён)
        ok = H[g] >= lvl; mode = 'pb20'
        if ok:
            entry_g = g; break
    # свечи выноса: от g0 до экстремума, доджи (тело ≤25% диапазона) не считаем
    nsw = 0
    for g in range(g0, ge + 1):
        rg = H[g] - L[g]
        if not (rg > 0 and abs(C[g] - O[g]) <= 0.25 * rg): nsw += 1
    res['extreme'] = round(sd * ext, dec)
    if nsw > 4:
        res['ckf'] = [4]; res['reasons'] = [f'свечей выноса {nsw} (>4)']; _why(res, f'Скип: свечей выноса {nsw}, допустимо ≤4', [4])
        return _out(res, 'skip', dirc, 'СКИП (вынос длиннее 4 свечей)')
    res['ck'] = sorted(set(res['ck'] + [4]))
    _why(res, f'Свечей выноса {nsw} (≤4)', [4])
    # широкий M5 FVG в 3 свечах перед экстремумом (контр-ножка выноса)
    bx = box.iloc[-20:]
    avgR = float((bx['High'] - bx['Low']).mean()) if len(bx) else 0.0
    wide = None
    for k in (ge - 1, ge):
        a, c_ = k - 2, k
        if a >= 0 and c_ < n and L[a] > H[c_] and (L[a] - H[c_]) >= 2 * avgR and avgR > 0:
            wide = (float(L[a] - H[c_]), a, c_); break
    if wide:
        res['ckf'] = [7]; t = f'широкий M5 FVG ({wide[0]:.{dec}f} ≥ 2× средней свечи Лондона) перед экстремумом'
        res['reasons'] = [t]; _why(res, 'Скип: ' + t, [7])
        return _out(res, 'skip', dirc, 'СКИП (широкий M5 FVG перед экстремумом)')
    leg = lowB - ext
    if entry_g is None or leg <= 0:
        if nowm >= 1110:
            _w = 'откат 20%'
            res['ckf'] = [5]; res['reasons'] = [f'{_w} не случилось до 18:30']; _why(res, f'Скип: {_w} не случилось до 18:30', [5])
            return _out(res, 'skip', dirc, f'СКИП ({_w} не случилось до 18:30)')
        _prob_set_C(res, F1, atr1, sd, ext, plus)
        return _out(res, 'prep', dirc, f'ВЫНОС ({"лоя" if sd == 1 else "хая"} бокса, ждём откат 20%)')
    if (d['rmin'].iloc[entry_g]) >= wb:
        res['ckf'] = [5]; res['reasons'] = ['откат 20% после 18:30']; _why(res, 'Скип: откат ≥20% позже 18:30', [5])
        return _out(res, 'skip', dirc, 'СКИП (вход позже 18:30)')
    lvl = ext + 0.2 * leg
    entry = max(lvl, float(O[entry_g]))   # вход по уровню отката 20%
    stop_f = ext - 0.1 * (entry - ext)
    R = entry - stop_f
    tp_f = entry + 3 * R
    atr_m = float((d['High'] - d['Low']).iloc[max(0, entry_g - 14):entry_g].mean())
    if R < 0.25 * atr_m:
        res['ckf'] = [9]; t = f'стоп {R:.{dec}f} меньше 0,25 ATR(M5) — не исполнить со спредом'
        res['reasons'] = [t]; _why(res, 'Скип: ' + t, [9])
        return _out(res, 'skip', dirc, 'СКИП (стоп слишком мал)')
    be_f = entry + 0.5 * (tp_f - entry)
    entry_r, stop_r, tp_r, be_r = sd * entry, sd * stop_f, sd * tp_f, sd * be_f
    _prob_set_C(res, F1, atr1, sd, ext, plus)
    plus = res['plus']
    cf = _counter_fvg(F1, sd, entry_r, tp_r)
    res['ck'] = sorted(set(res['ck'] + [5]))
    _why(res, 'Откат ≥20% длины выноса достигнут', [5])
    if cf is not None:
        res['ckf'] = [8]; t = f'встречный H1 FVG {fmtp(cf["lo"])}–{fmtp(cf["hi"])} внутри цели 1:3'
        res['reasons'] = [t]; _why(res, 'Скип: ' + t, [8])
        return _out(res, 'skip', dirc, 'СКИП (встречный H1 FVG внутри цели 1:3)')
    t_in = d.index[entry_g]      # свеча входа (вход по её закрытию, трекинг — со следующей свечи)
    end_utc = pd.Timestamp(dt.datetime.combine(today, dt.time(22, 0)) - dt.timedelta(hours=off), tz='UTC')
    res['ck'] = sorted(set(res['ck'] + [6, 7, 8, 9, 10] + plus))
    sig = dict(date=str(today), window='C', time=(t_in + pd.Timedelta(hours=off, minutes=0)).strftime('%H:%M'), t_utc=str(t_in),
               entry=round(entry_r, dec), stop=round(stop_r, dec), tp=round(tp_r, dec), be_at=round(be_r, dec),
               side='long' if sd == 1 else 'short', rr=3.0, end_utc=str(end_utc), ck=list(res['ck']), plus=list(plus), worse=[],
               prob=res['prob'], struct=res['struct']['rec'], sconf=res['struct'].get('conf'), sscore=res['struct'].get('score'), sv=2)
    res['signal'] = sig; res['new_signal'] = True
    _why(res, f'ВХОД: вероятность закрытия цели {res["prob"]}; выполнены пункты ' + _nums(res['ck']))
    return _out(res, 'entry', dirc, f'ВХОД ({sig["time"]}, {fmtp(entry_r)})')


def _prob_set_C(res, F1, atr1, sd, ext, plus):
    plus = list(plus)
    tol = 0.2 * atr1
    ext_r = sd * ext
    for f in F1:
        if f['dir'] == sd and f['inv_t'] is None and f['lo'] - tol <= ext_r <= f['hi'] + tol:
            plus.append(11); _why(res, f'батут: H1 FVG {f["lo"]:.5g}–{f["hi"]:.5g}, от него пошёл выкуп', [11]); break
    if 12 in plus: _why(res, 'по тренду (структура Swing H1 + Sub M15 совпадает со стороной входа)', [12])
    res['ck'] = sorted(set(res['ck'] + plus))
    _prob_set(res, plus, [], 'C')


def autopsy(sig, sd, d, res=None):
    """Короткий разбор закрытого по SL сигнала (≤3 фразы): как шла сделка, что было после стопа,
    что из рамки было против входа. Только по цифрам; визуальные пункты чек-листа не считаем."""
    try:
        R = abs(sig['entry'] - sig['stop'])
        if R <= 0: return ''
        t0 = pd.Timestamp(sig['t_utc'])
        aft = d[d.index > t0]
        sl_t = None
        for ts, r in aft.iterrows():
            if (r['Low'] <= sig['stop']) if sd == 1 else (r['High'] >= sig['stop']): sl_t = ts; break
        if sl_t is None: return ''
        pre = aft[aft.index < sl_t]
        mfe = 0.0
        if len(pre):
            mfe = ((pre['High'].max() - sig['entry']) if sd == 1 else (sig['entry'] - pre['Low'].min())) / R
        held = int((sl_t - t0).total_seconds() // 60) + 5
        hh = f'{held // 60} ч {held % 60} мин' if held >= 60 else f'{held} мин'
        p1 = ('сразу пошла против входа' if mfe < 0.15 else f'шла в плюс до +{mfe:.1f}R') + f', стоп через {hh}'
        post = aft[aft.index > sl_t]
        if len(post) < 6:
            p2 = 'после стопа данных пока мало'
        else:
            hit = None
            for ts, r in post.iterrows():
                if (r['High'] >= sig['tp']) if sd == 1 else (r['Low'] <= sig['tp']): hit = ts; break
            if hit is not None:
                tt = hit.tz_convert('Europe/Riga').strftime('%H:%M') if hit.tzinfo else str(hit)[11:16]
                p2 = f'после стопа цель {float(sig.get("rr") or 2):g}R достигнута в {tt} — стоп выбило'
            else:
                ex = ((sig['entry'] - post['Low'].min()) if sd == 1 else (post['High'].max() - sig['entry'])) / R
                p2 = 'после стопа цель не достигнута' + (f', цена ушла дальше против на {ex:.1f}R' if ex > 1.2 else '')
        bad = []
        for k, nm in (('trend_h1', 'H1'), ('trend_d1', 'D1')):
            tr = str((res or {}).get(k, {}).get('tr', '')).lower()
            if tr and ((sd == 1 and 'шорт' in tr) or (sd == -1 and 'лонг' in tr)):
                bad.append(nm)
        p3 = (' и '.join(bad) + ' против входа') if bad else ''
        return '; '.join(x for x in (p1, p2, p3) if x)
    except Exception:
        return ''


def _bepct(sig):
    try:
        return int(round(100 * (sig['be_at'] - sig['entry']) / (sig['tp'] - sig['entry'])))
    except Exception:
        return 70


def _track(res, d, sig, sd, dirc, fmtp):
    """Ведём сделку по барам. Цель = sig['rr'] R (по умолчанию 2), у S1 — 3R и закрытие по времени в 22:00 Рига
    (sig['end_utc'] — момент закрытия; бары с этого времени уже не учитываются)."""
    res['signal'] = sig
    if sig.get('ck'): res['ck'] = list(sig['ck']); res['ckf'] = []
    if sig.get('fx'): res['fx'] = sig['fx']
    rr = float(sig.get('rr') or 2)
    rtxt = f'{rr:g}R'
    after = d[d.index > pd.Timestamp(sig['t_utc'])]
    end_utc = pd.Timestamp(sig['end_utc']) if sig.get('end_utc') else None
    if end_utc is not None: after = after[after.index < end_utc]
    out = None; xt = None; armed = False; be = sig.get('be_at')
    for _, r in after.iterrows():
        stp = sig['entry'] if armed else sig['stop']
        tt_ = _.tz_convert('Europe/Riga').strftime('%H:%M') if _.tzinfo else None
        if (r['Low'] <= stp) if sd == 1 else (r['High'] >= stp): out = 'BE' if armed else 'SL'; xt = tt_; break
        if (r['High'] >= sig['tp']) if sd == 1 else (r['Low'] <= sig['tp']): out = 'TP'; xt = tt_; break
        if be and not armed and ((r['High'] >= be) if sd == 1 else (r['Low'] <= be)): armed = True
    if out is None and end_utc is not None and len(d) and d.index[-1] + pd.Timedelta(minutes=5) >= end_utc:
        # 22:00: ни цель, ни стоп — закрываем по рынку (последняя свеча до 22:00)
        px = float(after['Close'].iloc[-1]) if len(after) else float(sig['entry'])
        R = abs(sig['entry'] - sig['stop']) or 1e-12
        rres = (px - sig['entry']) * sd / R
        res['exit_time'] = '22:00'; res['exit_r'] = round(rres, 2)
        sg = f'{rres:+.1f}'.replace('.', ',')
        return _out(res, 'entry', dirc, f'ВХОД → закрыта в 22:00 ({sg}R)', tg='ЗАКРЫТА - 22:00')
    if out:
        res['exit_time'] = xt
    if out == 'TP':
        return _out(res, 'entry', dirc, f'ВХОД → TP 🎯 +{rtxt}', tg='ЗАКРЫТА - TP')
    if out == 'BE':
        return _out(res, 'entry', dirc, f'ВХОД → БУ 0R (стоп в безубытке после {_bepct(sig)}% пути)', tg='ЗАКРЫТА - БУ')
    if out == 'SL':
        res['autopsy'] = autopsy(sig, sd, d, res)
        return _out(res, 'skip', dirc, 'ВХОД → SL −1R', tg='ЗАКРЫТА - SL')
    return _out(res, 'entry', dirc, 'В СДЕЛКЕ')


# 28.09.2026 (по просьбе пользователя): уведомления/отчёты в Telegram должны показывать
# ТОЛЬКО короткое канонiческое слово статуса (СКИП / НАБЛЮДАЕМ / ВЫНОС / ВХОД /
# ЗАКРЫТА - TP / ЗАКРЫТА - SL) — без причин (они остаются только в `note`/`reasons` для
# карточек Пульта). tg_note по умолчанию берётся по статусу; явный tg= в _out()
# переопределяет его (нужно только для TP/SL, см. _track выше) — "В СДЕЛКЕ" НЕ входит
# в этот словарь: это статус ТОЛЬКО для ручной кнопки "ВОШЁЛ" в Пульте, в Telegram не шлётся.
_TG_DEFAULT = {'skip': 'СКИП', 'watch': 'НАБЛЮДАЕМ', 'prep': 'ВЫНОС', 'entry': 'ВХОД'}


def _out(res, status, direction, note, reasons=None, tg=None):
    res['line_status'] = status
    res['direction'] = direction
    res['note'] = note
    res['status_key'] = note
    res['tg_note'] = tg or _TG_DEFAULT.get(status, note)
    if reasons: res['reasons'] = reasons
    res['stale'] = False
    return res
