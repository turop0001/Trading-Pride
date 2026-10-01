#!/usr/bin/env python3
"""Контекст для карточек Пульта (01.10.2026): структура Swing / Sub, ликвидность, FVG H1, вероятность.
Структура НЕ является правилом входа — только рекомендация (LONG / SHORT / 50-50) и усилитель «По тренду»."""
import numpy as np
import pandas as pd


def _piv(H, L, n):
    ph, pl = [], []
    for i in range(n, len(H) - n):
        w = H[i - n:i + n + 1]
        if H[i] >= w.max() and (H[i - n:i] < H[i]).all(): ph.append((i, float(H[i])))
        w = L[i - n:i + n + 1]
        if L[i] <= w.min() and (L[i - n:i] > L[i]).all(): pl.append((i, float(L[i])))
    return ph, pl


def _trend(df, n):
    """df — бары OHLC. Тренд по двум последним вершинам и двум последним впадинам фрактала n."""
    H, L, C = df['High'].values.astype(float), df['Low'].values.astype(float), df['Close'].values.astype(float)
    ph, pl = _piv(H, L, n)
    if len(ph) < 2 or len(pl) < 2:
        return dict(tr=0, txt='мало данных', hi=None, lo=None, brk='')
    h1, h2 = ph[-2][1], ph[-1][1]
    l1, l2 = pl[-2][1], pl[-1][1]
    if h2 > h1 and l2 > l1: tr, txt = 1, 'HH/HL'
    elif h2 < h1 and l2 < l1: tr, txt = -1, 'LH/LL'
    elif h2 < h1 and l2 > l1: tr, txt = 0, 'сжатие'
    else: tr, txt = 0, 'расширение'
    brk = ''
    last = float(C[-1])
    if tr == 1 and last < l2: brk = 'слом вниз (close ниже HL)'; tr = 0
    elif tr == -1 and last > h2: brk = 'слом вверх (close выше LH)'; tr = 0
    return dict(tr=tr, txt=txt, hi=h2, lo=l2, brk=brk)


def _arrow(t):
    return '▲' if t == 1 else '▼' if t == -1 else '◆'


def h4_from_h1(h1c):
    return h1c[['Open', 'High', 'Low', 'Close']].resample('4h', label='left', closed='left').agg(
        {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()


def liquidity(h1c, d_loc, today, off, price, asia=None):
    """Несобранная ликвидность: фракталы H1 (n=3) и D1 (n=2), экстремумы вчерашнего дня и вчерашнего Лондона.
    Возвращает список dict(p, name, kind='hi'|'lo'), только те уровни, которые цена ещё НЕ снимала."""
    out = []
    H, L = h1c['High'].values.astype(float), h1c['Low'].values.astype(float)
    T = h1c.index
    ph, pl = _piv(H, L, 3)
    for i, v in ph:
        if not (H[i + 1:] > v).any(): out.append(dict(p=v, name='хай H1 ' + (T[i] + pd.Timedelta(hours=off)).strftime('%d.%m %H:%M'), kind='hi'))
    for i, v in pl:
        if not (L[i + 1:] < v).any(): out.append(dict(p=v, name='лой H1 ' + (T[i] + pd.Timedelta(hours=off)).strftime('%d.%m %H:%M'), kind='lo'))
    dd = h1c[['Open', 'High', 'Low', 'Close']].resample('1D').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    if len(dd) >= 6:
        DH, DL = dd['High'].values.astype(float), dd['Low'].values.astype(float)
        qh, ql = _piv(DH, DL, 2)
        for i, v in qh:
            if not (DH[i + 1:] > v).any(): out.append(dict(p=v, name='хай D1 ' + dd.index[i].strftime('%d.%m'), kind='hi'))
        for i, v in ql:
            if not (DL[i + 1:] < v).any(): out.append(dict(p=v, name='лой D1 ' + dd.index[i].strftime('%d.%m'), kind='lo'))
    # сессии: вчерашний день (по Риге) и вчерашний Лондон 11:00–16:25
    try:
        rd, rm = d_loc['rdate'].values, d_loc['rmin'].values
        dates = sorted(set(rd))
        prev = [x for x in dates if x < today]
        if prev:
            pdte = prev[-1]
            m = d_loc[rd == pdte]
            for nm, mm in (('вчера', m), ('Лондон вчера', m[(m['rmin'] >= 660) & (m['rmin'] < 985)])):
                if len(mm) < 5: continue
                hi, lo = float(mm['High'].max()), float(mm['Low'].min())
                after = d_loc[d_loc.index > mm.index[-1]]
                if not (after['High'].values > hi).any(): out.append(dict(p=hi, name='хай ' + nm, kind='hi'))
                if not (after['Low'].values < lo).any(): out.append(dict(p=lo, name='лой ' + nm, kind='lo'))
    except Exception:
        pass
    return out


def build(d, h1, now_utc, off, today, price, completed, resample_h1):
    """d — закрытые M5 (UTC), h1 — часовые бары (UTC) или None. Возвращает dict контекста."""
    h1c = completed(h1, now_utc, 60) if h1 is not None and len(h1) else resample_h1(d)
    if len(h1c) < 60:
        h1c = completed(resample_h1(d), now_utc, 60)
    ctx = dict(h1c=h1c)
    sw = _trend(h4_from_h1(h1c).iloc[-120:], 2) if len(h1c) >= 60 else dict(tr=0, txt='мало данных', hi=None, lo=None, brk='')
    sb = _trend(h1c.iloc[-300:], 3) if len(h1c) >= 60 else dict(tr=0, txt='мало данных', hi=None, lo=None, brk='')
    if sw['tr'] == sb['tr'] and sw['tr'] != 0: rec = 'LONG' if sw['tr'] == 1 else 'SHORT'
    else: rec = '50/50'
    ctx.update(swing=sw, sub=sb, rec=rec)
    return ctx


def struct_line(ctx, price, liq, fm):
    """Короткий нарратив без цифр: части через ' | ' (Пульт рисует каждую отдельной строкой)."""
    sw, sb, rec = ctx['swing'], ctx['sub'], ctx['rec']
    up = sorted([x for x in liq if x['p'] > price], key=lambda x: x['p'])
    dn = sorted([x for x in liq if x['p'] < price], key=lambda x: -x['p'])
    parts = []
    hi, lo = sw.get('hi'), sw.get('lo')
    if hi and lo and hi > lo:
        f = (price - lo) / (hi - lo)
        if sw['tr'] == 1: parts.append('откат внутри восходящего Swing' if f < 0.5 else 'импульс в восходящем Swing')
        elif sw['tr'] == -1: parts.append('откат внутри нисходящего Swing' if f > 0.5 else 'импульс в нисходящем Swing')
        else: parts.append('цена внутри диапазона Swing')
    if sw.get('brk'): parts.append(sw['brk'])
    parts.append({'LONG': 'вероятнее вверх', 'SHORT': 'вероятнее вниз', '50/50': 'направление неясно'}[rec])
    liqs = []
    if up: liqs.append('↑ ' + up[0]['name'])
    if dn: liqs.append('↓ ' + dn[0]['name'])
    if liqs: parts.append('Ликвидность: ' + ' · '.join(liqs))
    return ' | '.join(parts)


def prob_word(n_plus, n_worse):
    s = n_plus - n_worse
    return 'высокая' if s >= 2 else 'средняя' if s >= 0 else 'низкая'


def box_pos(d_loc, today, price, bH, bL, end_m):
    """Цена относительно бокса одним словом: Выше / Ниже / Внутри / Поглотила (после бокса сняты обе границы)."""
    m = d_loc[(d_loc['rdate'] == today) & (d_loc['rmin'] >= end_m)]
    if len(m) and (m['High'].values > bH).any() and (m['Low'].values < bL).any():
        return 'Поглотила'
    return 'Выше' if price > bH else 'Ниже' if price < bL else 'Внутри'
