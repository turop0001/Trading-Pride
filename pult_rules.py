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
    end = df.index + pd.Timedelta(minutes=minutes)
    return df[end <= pd.Timestamp(now_utc, tz='UTC')]


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
            A_(24, b, ('батут ' + ', '.join(b)) if b else 'батута под выносом нет')
        # встречные на пути
        for nm, F, n_ in (('H1', F1, 21), ('H4', F4, 21)):
            cand = [f for f in F if f['dir'] == -sd and f['inv_t'] is None and ((f['lo'] > price) if sd == 1 else (f['hi'] < price))]
            if cand:
                f = min(cand, key=lambda z: z['lo']) if sd == 1 else max(cand, key=lambda z: z['hi'])
                lvl = f['lo'] if sd == 1 else f['hi']
                pre = ''
                if tp is not None:
                    pre = ', до цели 2R' if ((lvl < tp) if sd == 1 else (lvl > tp)) else ', за целью 2R'
                A_(n_, True, f'встречный {nm} {rng(f)}{pre}')
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


def analyze(sym, d, window, now_utc, off, prev=None):
    """d — 5m OHLC (UTC index) за ~10 дней. prev — прошлое состояние инструмента (для сигнала/TP/SL).
    Возвращает dict со статусом в коротком формате Пульта + список причин."""
    prev = prev or {}
    if window == 'C':
        d2 = _completed(d, now_utc, 5).copy()
        return _analyze_C(sym, d2, now_utc, off, prev)
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
                p2 = f'после стопа цель 2R достигнута в {tt} — стоп выбило'
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


def _track(res, d, sig, sd, dirc, fmtp):
    res['signal'] = sig
    if sig.get('ck'): res['ck'] = list(sig['ck']); res['ckf'] = []
    if sig.get('fx'): res['fx'] = sig['fx']
    after = d[d.index > pd.Timestamp(sig['t_utc'])]
    out = None
    for _, r in after.iterrows():
        if (r['Low'] <= sig['stop']) if sd == 1 else (r['High'] >= sig['stop']): out = 'SL'; xt = _.tz_convert('Europe/Riga').strftime('%H:%M') if _.tzinfo else None; break
        if (r['High'] >= sig['tp']) if sd == 1 else (r['Low'] <= sig['tp']): out = 'TP'; xt = _.tz_convert('Europe/Riga').strftime('%H:%M') if _.tzinfo else None; break
    if out:
        res['exit_time'] = xt
    if out == 'TP':
        return _out(res, 'entry', dirc, 'ВХОД → TP 🎯 +2R', tg='ЗАКРЫТА - TP')
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
