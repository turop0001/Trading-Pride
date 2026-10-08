#!/usr/bin/env python3
"""Тип A, версия S1 (01.10.2026) — правила по результатам теста 5 лет (Dukascopy M5, 7 инструментов,
10.2021–09.2026): Азия + V-разворот + M5 FVG выноса + вход (3 сильные свечи или откат ≥30%) + цепочка H1 ≥2,
стоп = экстремум выноса − 0,3 ATR(M5, 14), цель 3R, держим до 22:00 Рига. Одна сделка на инструмент в день
(первый подходящий кандидат). Результат теста: 238 сделок, 4,0/мес, WR 38%, +108R, просадка −8R, серия SL 7.

Логика перенесена из mech.py (скрипты_тест_5лет_v8.tgz) без изменений — решение принимается по закрытой
свече, вход по открытию следующей. Шорт считается зеркально: цены умножаются на −1 (хай ↔ лоу).
"""
import numpy as np
import pandas as pd

ASIA = (180, 600)      # 03:00–10:00 Рига
WIN = (600, 840)       # окно входа 10:00–14:00 Рига
END_M = 1320           # 22:00 Рига — закрытие сделки
BUF = 0.3              # буфер стопа, ATR(M5, 14)
RR = 2.0               # цель, R (с 01.10.2026: 1:2)
VBARS = 7              # 07.10.2026: V-разворот — не позже 7 значимых свечей после экстремума
DOJI = 0.25            # доджи: тело <=25% диапазона, в счёт свечей V-разворота не идут
FVWIN = 5               # 08.10.2026: окно поиска M5 FVG выноса — последние 5 свечей выноса
MINSW = 0.5            # 07.10.2026: минимальный вынос за границу Азии, в ATR(M5, 14)
SWTRG = 1.5            # 08.10.2026: вынос ≤1,5 ATR → триггер входа = ≥2 сильных свечи выкупа (откат 30% не используется); больше 1,5 ATR — как раньше (≥3 сильных ИЛИ откат ≥30%)
STRONG_SMALL = 2


def struct(Hh, Lh, Ch):
    """Структура H1: зигзаг с откатом ≥30% ноги, тренд = закрытие H1 за последней вершиной/впадиной.
    Возвращает (тренд, цепочка): цепочка = min(подряд растущих хаёв, подряд растущих лоёв) при тренде вверх."""
    n = len(Hh)
    tr = np.zeros(n, int); chain = np.zeros(n, int)
    highs = []; lows = []
    dirz = 1; ext = 0; Lp = Lh[0]; Hp = Hh[0]; ctr = 0; cpl = (np.nan, -1); cph = (np.nan, -1)

    def cn(v):
        c = 0
        for a in range(len(v) - 1, 0, -1):
            if v[a] > v[a - 1]: c += 1
            else: break
        return c
    for q in range(1, n):
        if not np.isnan(cph[0]) and Ch[q] > cph[0]: ctr = 1
        if not np.isnan(cpl[0]) and Ch[q] < cpl[0]: ctr = -1
        if dirz == 1:
            if Hh[q] >= Hh[ext]: ext = q
            elif Hh[ext] - Lh[q] >= 0.3 * max(Hh[ext] - Lp, 1e-12):
                cph = (Hh[ext], ext); highs.append(Hh[ext]); Hp = Hh[ext]; dirz = -1; ext = q
        else:
            if Lh[q] <= Lh[ext]: ext = q
            elif Hh[q] - Lh[ext] >= 0.3 * max(Hp - Lh[ext], 1e-12):
                cpl = (Lh[ext], ext); lows.append(Lh[ext]); Lp = Lh[ext]; dirz = 1; ext = q
        tr[q] = ctr; chain[q] = min(cn(highs), cn(lows)) if ctr == 1 else 0
    return tr, chain


def h1_from_m5(d):
    return d[['Open', 'High', 'Low', 'Close']].resample('1h', label='left', closed='left').agg(
        {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()


def chain_series(h1, sd):
    H, L, C = h1['High'].values.astype(float), h1['Low'].values.astype(float), h1['Close'].values.astype(float)
    if sd == -1: H, L, C = -L, -H, -C
    tr, ch = struct(H, L, C)
    return h1.index, tr, ch


def analyze_day(d, today, off, sd, h1=None):
    """Разбор дня для стороны sd (+1 лонг, −1 шорт). d — ЗАКРЫТЫЕ бары M5 (UTC-индекс), h1 — часовые бары (UTC).
    Возвращает dict: cand (первый подходящий кандидат или None), start (индекс первого выноса), last_chain."""
    loc = d.index + pd.Timedelta(hours=off)
    rdate = np.array([x.date() for x in loc])
    rm = np.array([x.hour * 60 + x.minute for x in loc])
    O0, H0, L0, C0 = [d[c].values.astype(float) for c in ('Open', 'High', 'Low', 'Close')]
    if sd == 1: O, H, L, C = O0, H0, L0, C0
    else: O, H, L, C = -O0, -L0, -H0, -C0
    n = len(O)
    atr = pd.Series(H - L).rolling(14).mean().values
    ai = np.flatnonzero((rdate == today) & (rm >= ASIA[0]) & (rm < ASIA[1]))
    wi = np.flatnonzero((rdate == today) & (rm >= WIN[0]) & (rm < WIN[1]))
    out = dict(sd=sd, n=n, cand=None, start=None, last_chain=None)
    if len(ai) < 60 or len(wi) == 0:
        return out
    aL = float(L[ai].min())
    if h1 is None: h1 = h1_from_m5(d)
    hidx, htr, hch = chain_series(h1, sd)
    hvals = hidx.values.astype('datetime64[ns]')
    idx_ns = d.index.values.astype('datetime64[ns]')

    def chain_at(g):
        # последняя ЗАКРЫТАЯ часовая свеча к моменту закрытия свечи g
        lim = idx_ns[g] + np.timedelta64(5, 'm') - np.timedelta64(1, 'h')
        c = int(np.searchsorted(hvals, lim, side='right')) - 1
        if c < 30: return 0, 0
        return int(htr[c]), int(hch[c])

    out['chain_now'] = chain_at(n - 1)[1]
    start = ext = ge = None; nsw = 0
    for g in wi:
        if rm[g] + 5 >= WIN[1]: break          # следующая свеча (вход) должна начаться до 14:00
        if start is None:
            if L[g] < aL: start = g; ext = L[g]; ge = g; nsw = 1
            continue
        if L[g] < ext: ext = L[g]; ge = g; nsw += 1; continue
        if not (C[g] > O[g]) or ge >= g: continue
        if not atr[g] > 0: continue
        leg = aL - ext
        ret = (C[g] - ext) / leg if leg > 0 else 9
        rel = slice(ge + 1, g + 1)
        cl, op, hh, ll = C[rel], O[rel], H[rel], L[rel]
        strong = int(((cl > op) & ((cl - op) >= 0.6 * (hh - ll) + 1e-12)).sum())
        # 07.10.2026: V-разворот — свеча входа не позже 7 значимых свечей после экстремума выноса (доджи с телом <=25% диапазона не считаются)
        nbars = sum(1 for j in range(ge + 1, g + 1) if (H[j] - L[j]) > 0 and abs(C[j] - O[j]) > DOJI * (H[j] - L[j]))
        f2 = nbars <= VBARS
        # 07.10.2026: вынос не меньше 0,5 ATR(M5, 14) за границу Азии — иначе откат 30% от мелкого выноса считается шумом
        f2 = f2 and (aL - ext) >= MINSW * atr[g]
        fv5 = None
        # 08.10.2026: M5 FVG выноса ищется только среди последних FVWIN (=5) свечей выноса (FVG целиком внутри свечей ge-FVWIN+1 .. ge), а не по всему выносу
        for c_ in range(ge, ge - (FVWIN - 3) - 1, -1):
            a_ = c_ - 2
            if a_ >= start and L[a_] > H[c_]: fv5 = L[a_]; break
        ov5 = (fv5 is not None) and (C[rel].max() > fv5)
        f4 = (fv5 is None) or bool(ov5)
        # 08.10.2026: триггер зависит от размера выноса на момент свечи (5 лет, 7 инструментов: просадка 13R → 7R, серия SL 9 → 7, WR 52.1 → 54.3%, ΣR 829.9 → 696.1)
        if (aL - ext) / atr[g] <= SWTRG: f7 = strong >= STRONG_SMALL
        else: f7 = (strong >= 3) or (ret >= 0.3)
        trd, chn = chain_at(g)
        out['last_chain'] = chn
        if f2 and f4 and f7:   # цепочка H1 как правило убрана 01.10.2026 (структура — только контекст)
            e = O[g + 1] if g + 1 < n else None
            out['cand'] = dict(g=int(g), ge=int(ge), start=int(start), ext_f=float(ext), atr=float(atr[g]), nbars=int(nbars), sw_atr=float((aL - ext) / atr[g]),
                               strong=strong, ret=float(ret), nsw=nsw, chain=chn, t_g=d.index[g])
            out['start'] = start
            return out
    out['start'] = start
    out['last_ext_f'] = None if ext is None else float(ext)
    out['last_sw_atr'] = None if ext is None or not atr[n - 1] > 0 else float((aL - ext) / atr[n - 1])
    if start is not None and out['last_chain'] is None:
        out['last_chain'] = chain_at(n - 1)[1]
    return out
