#!/usr/bin/env python3
"""Тип A v2.03 (28.10.2026) — правила как в советнике PultTraderAC_v1_06 (EvalSym, вход A).

Азия 03:00–10:00 Рига; окно выноса 10:00–13:00; вынос границы Азии тенью или телом (одна сторона; обе одной свечой — скип дня);
вынос к моменту сигнала от 2,4 до 3,0 ATR(M5,14); сигнал = закрытие M5 за низ/верх БЛИЖАЙШЕГО к экстремуму M5 FVG выноса (зазор ≥0,2 ATR, в последних 4 свечах
выноса), без закрытий за уровнем между FVG и сигналом; вход по открытию следующей свечи (свеча входа закрывается до 13:00);
стоп = экстремум выноса ± 0,5 ATR (риск от 0,25 до 3,5 ATR, иначе скип); скипы: FB (хай/лой двух прошлых дней ближе 3 ATR за экстремумом),
FAa (инвертированный H1 FVG по направлению ≥0,5 ATR(H1) с инверсией внутри 00:00–10:00 сегодня); выход: лесенка 2/2 без TP, 22:00 Рига.
Работает по ЗАКРЫТЫМ M5 (решение по закрытой свече, вход по открытию следующей) — тот же принцип, что и в советнике.
"""
import datetime as dt
import numpy as np
import pandas as pd

ASIA = (180, 600)
WIN = (600, 780)
END_M = 1320
MINSW, MAXSW = 2.4, 3.0
GAP = 0.2
BUF = 0.5
MINRISK = 0.25
MAXRISK = 3.5   # 28.10.2026: стоп не шире 3,5 ATR(M5) (5 лет: +190R/DD −10,7R против +197R/−10,8R, убирает стопы 5–8 ATR)
FB = 3.0
FAA_MIN = 0.5
FVG_MIN = 0.15
LAD_STEP, LAD_LAG = 2.0, 2.0
LB = 4


def _faa(d, t_in, sd, day0, win_end, fvgs):
    h = d[(d.index < t_in) & (d.index >= t_in - pd.Timedelta(days=12))][['Open', 'High', 'Low', 'Close']].resample(
        '1h', label='left', closed='left').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    h = h[h.index + pd.Timedelta(hours=1) <= t_in]
    if len(h) < 30: return False
    atr1 = float((h['High'] - h['Low']).iloc[-14:].mean())
    F = fvgs(h.iloc[-240:], FVG_MIN * atr1)
    for f in F:
        if f['dir'] == sd and f['inv_t'] is not None and (f['hi'] - f['lo']) >= FAA_MIN * atr1 and day0 <= f['inv_t'] < win_end:
            return True
    return False


def _fb(d, today, off, sd, ext, at):
    day0 = pd.Timestamp(dt.datetime.combine(today, dt.time(0, 0)) - dt.timedelta(hours=off), tz='UTC')
    pv = d[(d.index < day0) & (d.index >= day0 - pd.Timedelta(days=6))]
    if not len(pv): return None
    rd = np.array([x.date() for x in (pv.index + pd.Timedelta(hours=off))])
    days = sorted(set(rd))[-2:]
    best = None
    for dd in days:
        x = pv[rd == dd]
        lv = float(x['High'].max()) if sd == -1 else float(x['Low'].min())
        v = (lv - ext) if sd == -1 else (ext - lv)
        if v > 0:
            v /= at
            best = v if best is None else min(best, v)
    return best


def scan(d, today, off, nowm, fvgs, live_open=None):
    """d — ЗАКРЫТЫЕ M5. Возвращает dict: st: nodata|watch|prep|skip|wait_entry|entry (+sd, boxH, boxL, ext, sw, sig, why, ck, ckf, entry, stop, R, t_in).
    live_open — (индекс, Open) формирующейся свечи после последней закрытой (вход без ожидания её закрытия)."""
    loc = d.index + pd.Timedelta(hours=off)
    rdate = np.array([x.date() for x in loc]); rm = np.array([x.hour * 60 + x.minute for x in loc])
    O, H, L, C = [d[c].values.astype(float) for c in ('Open', 'High', 'Low', 'Close')]
    n = len(O)
    atr = pd.Series(H - L).rolling(14).mean().values
    ai = np.flatnonzero((rdate == today) & (rm >= ASIA[0]) & (rm < ASIA[1]))
    if len(ai) < 60:
        return dict(st='nodata')
    boxH, boxL = float(H[ai].max()), float(L[ai].min())
    out = dict(boxH=boxH, boxL=boxL, ck=[1], ckf=[], sd=0)
    wi = np.flatnonzero((rdate == today) & (rm >= WIN[0]) & (rm < WIN[1]))
    sd = 0; start = e = None; ext = 0.0; sig = None; sw = None; at = None; lastsw = None; latched = False
    for i in wi:
        if sd == 0:
            up = H[i] > boxH; dn = L[i] < boxL
            if up and dn:
                out.update(st='skip', why='обе стороны Азии сняты одной свечой', ckf=[2]); return out
            if not (up or dn): continue
            sd = -1 if up else 1; start = int(i); e = int(i); ext = float(H[i] if up else L[i])
        else:
            if sd == -1 and H[i] > ext: ext = float(H[i]); e = int(i)
            if sd == 1 and L[i] < ext: ext = float(L[i]); e = int(i)
        at = atr[i]
        if not (at and at == at and at > 0): continue
        sw = ((ext - boxH) if sd == -1 else (boxL - ext)) / at
        lastsw = sw
        # 28.10.2026: скип окончательный — как только вынос в ATR ушёл за MAXSW (до 13:00), день пропущен, поздний возврат в коридор входа не даёт
        if sw >= MAXSW and rm[i] + 5 < WIN[1]: latched = True; break
        if sw < MINSW or sw >= MAXSW or rm[i] + 5 >= WIN[1]: continue
        found = False
        # 28.10.2026: берём ближайший к экстремуму FVG (самая поздняя свеча c из последних LB свечей выноса с зазором ≥ GAP ATR), а не самый ранний
        tgt = None
        for c0 in range(e, max(e - LB, start - 2, 2) - 1, -1):
            g0 = (L[c0] - H[c0 - 2]) if sd == -1 else (L[c0 - 2] - H[c0])
            if g0 >= GAP * at and i > c0: tgt = c0; break
        for c in ([tgt] if tgt is not None else []):
            if sd == -1: gap = L[c] - H[c - 2]; lo = H[c - 2]
            else: gap = L[c - 2] - H[c]; lo = L[c - 2]
            if gap < GAP * at or i <= c: continue
            if sd == -1: ok = C[i] < lo and not (c + 1 < i and C[c + 1:i].min() < lo)
            else: ok = C[i] > lo and not (c + 1 < i and C[c + 1:i].max() > lo)
            if ok: found = True; break
        if found: sig = int(i); break
    if sd == 0:
        out.update(st='skip' if nowm >= WIN[1] else 'watch')
        if out['st'] == 'skip': out.update(why='вынос границы Азии не случился до 13:00', ckf=[2])
        return out
    out.update(sd=sd, ext=ext, start=start, sw=lastsw, at=at, sweep_time=(d.index[start] + pd.Timedelta(hours=off)).strftime('%H:%M'), ck=[1, 2])
    if sig is None:
        if latched:
            out.update(st='skip', why=f'вынос {lastsw:.2f} ATR — больше {MAXSW:g} ATR, день пропущен окончательно', ckf=[3])
        elif nowm >= WIN[1]:
            if lastsw is not None and lastsw >= MAXSW:
                out.update(st='skip', why=f'вынос {lastsw:.2f} ATR — больше {MAXSW:g} ATR', ckf=[3])
            elif lastsw is not None and lastsw < MINSW:
                out.update(st='skip', why=f'вынос {lastsw:.2f} ATR — меньше {MINSW:g} ATR', ckf=[3])
            else:
                out.update(st='skip', why='инверсии M5 FVG выноса не было до 13:00', ckf=[4], ck=[1, 2, 3])
        else:
            out.update(st='prep')
        return out
    out.update(ck=[1, 2, 3, 4], sig=sig, sw=sw)
    if sig + 1 < n: entry = float(O[sig + 1]); t_in = d.index[sig + 1]
    elif live_open is not None: t_in, entry = live_open
    else:
        out.update(st='wait_entry'); return out
    stop = ext + BUF * at if sd == -1 else ext - BUF * at
    R = (stop - entry) if sd == -1 else (entry - stop)
    if R <= 0 or R < MINRISK * at:
        out.update(st='skip', why=f'стоп {max(R,0)/at:.2f} ATR — меньше {MINRISK:g} ATR', ckf=[5]); return out
    if R > MAXRISK * at:
        out.update(st='skip', why=f'стоп {R/at:.2f} ATR — шире {MAXRISK:g} ATR', ckf=[5]); return out
    out['ck'] = [1, 2, 3, 4, 5]
    fb = _fb(d, today, off, sd, ext, at)
    if fb is not None and fb <= FB:
        out.update(st='skip', why=f'хай/лой прошлых дней в {fb:.1f} ATR за экстремумом — ближе {FB:g} ATR', ckf=[6]); return out
    out['ck'] = [1, 2, 3, 4, 5, 6]
    day0 = pd.Timestamp(dt.datetime.combine(today, dt.time(0, 0)) - dt.timedelta(hours=off), tz='UTC')
    if _faa(d, t_in, sd, day0, day0 + pd.Timedelta(minutes=ASIA[1]), fvgs):
        out.update(st='skip', why='инвертированный H1 FVG по направлению внутри Азии (FAa)', ckf=[7]); return out
    out['ck'] = [1, 2, 3, 4, 5, 6, 7, 8]
    out.update(st='entry', entry=entry, stop=float(stop), R=float(R), t_in=t_in, atr_sig=float(at))
    return out
