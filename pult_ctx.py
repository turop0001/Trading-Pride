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


PCT, MAXPB, BUF, BUILD_BARS, BUILD_PCT = 0.35, 0.70, 0.25, 12, 0.25
SOFT = True; SOFTPCT = 0.2


def _atr(df, n=14):
    pc = df['Close'].shift()
    tr = pd.concat([df['High'] - df['Low'], (df['High'] - pc).abs(), (df['Low'] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().bfill().values


def _dyn(df, start=0, k=1.0, soft_on=None):
    """Динамический подход к структуре (видео «Динамический подход» + уточнения 01.10.2026).
    Диапазон коррекции — от HL (LH) до экстремума. Откат >=35% диапазона создаёт HH (LL); при затяжном билдинге
    ликвидности/консолидации достаточно >=25% за 12 свечей. Свежий LH/HL (откатный экстремум, подтверждённый возвратом >=20%) — якорь раннего CHoCH (закрытие телом за ним). HL (LH) рождается только после закрепления ТЕЛОМ за HH (LL)
    не менее чем на 0.25 ATR. Слом — закрытие телом за HL (LH). Откат >70% — структура под вопросом."""
    sf = SOFT if soft_on is None else soft_on
    H, L, C = (df[c].values.astype(float) for c in ('High', 'Low', 'Close'))
    A = _atr(df) * k
    n = len(df)
    hi = lo = start; tr = 0; i0 = start + 1
    for i in range(start + 1, n):
        if H[i] > H[hi]: hi = i
        if L[i] < L[lo]: lo = i
        if H[hi] - L[lo] >= 3 * A[i]:
            tr = 1 if lo < hi else -1; i0 = i + 1; break
    if tr == 0: return None
    piv = []; ev = []; evlv = []; deep = False
    if tr == 1: anc = (lo, L[lo]); ext = (hi, H[hi]); piv.append((lo, L[lo], 'L'))
    else: anc = (hi, H[hi]); ext = (lo, L[lo]); piv.append((hi, H[hi], 'H'))
    pend = None; sb = None; soft = None
    for i in range(i0, n):
        up = tr == 1
        softbrk = sf and pend is not None and soft is not None and ((C[i] < soft[1] - BUF * A[i]) if up else (C[i] > soft[1] + BUF * A[i]))
        if softbrk or ((C[i] < anc[1] - BUF * A[i]) if up else (C[i] > anc[1] + BUF * A[i])):
            if softbrk: piv.append((soft[0], soft[1], 'L' if up else 'H'))
            evlv.append(soft[1] if softbrk else anc[1])
            ev.append((i, 'CHoCH↓' if up else 'CHoCH↑'))
            hp = pend if pend else ext
            if not pend: piv.append((ext[0], ext[1], 'H' if up else 'L'))
            j = hp[0] + int(np.argmin(L[hp[0]:i + 1]) if up else np.argmax(H[hp[0]:i + 1]))
            anc = (hp[0], hp[1]); ext = (j, L[j] if up else H[j]); tr = -tr; pend = None; deep = False
            continue
        if pend is None:
            # новый экстремум фиксируется только закрытием ТЕЛОМ за прежним (тень без закрытия — снятие ликвидности)
            if (C[i] > ext[1]) if up else (C[i] < ext[1]):
                j = ext[0] + 1 + int(np.argmax(H[ext[0] + 1:i + 1]) if up else np.argmin(L[ext[0] + 1:i + 1]))
                ext = (j, H[j] if up else L[j])
            rng = max(abs(ext[1] - anc[1]), 1e-9)
            # глубина отката — по самому глубокому откатному экстремуму после последней точки (а не только текущей свече)
            dep = ((ext[1] - L[ext[0] + 1:i + 1].min()) if up else (H[ext[0] + 1:i + 1].max() - ext[1])) / rng if i > ext[0] else 0.0
            if i - ext[0] >= 3 and (dep >= PCT or (dep >= BUILD_PCT and i - ext[0] >= BUILD_BARS)):
                pend = ext; piv.append((ext[0], ext[1], 'H' if up else 'L')); sb = i; soft = None
        else:
            if sf:
                if soft is None and ((L[i] < L[sb]) if up else (H[i] > H[sb])): sb = i
                elif soft is None and sb is not None:
                    pr = (pend[1] - L[sb]) if up else (H[sb] - pend[1])
                    if ((H[i] - L[sb]) if up else (H[sb] - L[i])) >= SOFTPCT * max(pr, 1e-9) and i > sb: soft = (sb, L[sb] if up else H[sb])
            if (C[i] > pend[1] + BUF * A[i]) if up else (C[i] < pend[1] - BUF * A[i]):
                j = pend[0] + int(np.argmin(L[pend[0]:i + 1]) if up else np.argmax(H[pend[0]:i + 1]))
                piv.append((j, L[j] if up else H[j], 'L' if up else 'H'))
                dp = ((pend[1] - L[j]) if up else (H[j] - pend[1])) / max(abs(pend[1] - anc[1]), 1e-9)
                deep = dp > MAXPB
                ev.append((i, 'BOS↑' if up else 'BOS↓'))
                anc = (j, L[j] if up else H[j]); ext = (i, H[i] if up else L[i]); pend = None
    e = pend if pend else ext
    cur = C[-1]
    rng = max(abs(e[1] - anc[1]), 1e-9)
    dep = ((e[1] - cur) if tr == 1 else (cur - e[1])) / rng
    return dict(tr=tr, anc=anc, ext=e, pend=pend is not None, dep=dep, deep=deep or dep > MAXPB, ev=ev, piv=piv, n=n, evlv=evlv)


def _trend_dyn(df, start=0, k=1.0, soft_on=None):
    r = _dyn(df, start, k, soft_on)
    if r is None: return dict(tr=0, txt='мало данных', hi=None, lo=None, brk='')
    tr = r['tr']; a, e = r['anc'][1], r['ext'][1]
    hi, lo = (e, a) if tr == 1 else (a, e)
    brk = ''
    if r['ev'] and r['ev'][-1][0] >= r['n'] - 6 and r['ev'][-1][1].startswith('CHoCH'):
        brk = 'слом вниз (закрытие телом за HL)' if r['ev'][-1][1].endswith('↓') else 'слом вверх (закрытие телом за LH)'
        try:
            bi = r['ev'][-1][0]; lv = r['evlv'][-1] if r.get('evlv') else None
            ts = df.index[bi]; step = pd.Timedelta(minutes=60) if (len(df) > 1 and (df.index[1] - df.index[0]) >= pd.Timedelta(minutes=60)) else pd.Timedelta(minutes=15)
            te = ts + step   # время закрытия свечи слома
            te = te.tz_convert('Europe/Riga') if te.tzinfo else te.tz_localize('UTC').tz_convert('Europe/Riga')
            cl = float(df['Close'].values[bi]); fm = (lambda v: ('%.5f' % v) if v < 20 else ('%.2f' % v))
            brk += ' · %s Рига, закрытие %s' % (te.strftime('%d.%m %H:%M'), fm(cl)) + (' (уровень %s)' % fm(lv) if lv is not None else '')
        except Exception:
            pass
    txt = 'HH/HL' if tr == 1 else 'LH/LL'
    if r['dep'] > MAXPB: txt += ', откат глубже 70%'
    return dict(tr=tr, txt=txt, hi=hi, lo=lo, brk=brk, dep=r['dep'], deep=r['dep'] > MAXPB, piv=r['piv'])


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
    sw = dict(tr=0, txt='мало данных', hi=None, lo=None, brk=''); sb = dict(sw)
    if len(h1c) >= 60:
        # Swing — структура H1 за последние 7 дней; Sub — структура M15 внутри коридора последней ноги Swing
        h1w = h1c[h1c.index > h1c.index[-1] - pd.Timedelta(days=7)]
        try:
            sw = _trend_dyn(h1w, 0, 1.0, False)   # 02.10.2026: Swing H1 — слом только за настоящим LH/HL (без «раннего» якоря); новый LH/HL рождается после BOS за последним LL/HH
            t0 = h1w.index[0]
            if sw.get('piv') and len(sw['piv']) >= 2:
                t0 = h1w.index[min(sw['piv'][-2][0], len(h1w) - 1)]
            m15 = d[['Open', 'High', 'Low', 'Close']].resample('15min', label='left', closed='left').agg(
                {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
            m15 = m15[m15.index >= t0 - pd.Timedelta(hours=1)]
            sb = _trend_dyn(m15, 0, 0.6) if len(m15) > 40 else dict(tr=0, txt='мало данных', hi=None, lo=None, brk='')
        except Exception:
            sw = _trend(h1c.iloc[-168:], 3); sb = _trend(h1c.iloc[-120:], 2)
    # направление по Swing H1; Sub против Swing = откат внутри тренда (видео «Динамический подход», пример EURUSD)
    sc = 2.0 * sw['tr']
    if sw['tr'] != 0:
        sc += sb['tr'] * 1.0                      # Sub по тренду усиливает, против — ослабляет (откат внутри тренда)
        if sw.get('brk'): sc *= 0.5                # свежий слом структуры — доверие ниже
        if sw.get('deep'): sc -= 0.5 * sw['tr']     # откат глубже 70% — структура под вопросом
    else:
        sc = 0.5 * sb['tr']
    rec = 'LONG' if sc >= 1 else 'SHORT' if sc <= -1 else '50/50'
    conf = 'высокая' if abs(sc) >= 3 else 'средняя' if abs(sc) >= 1.5 else 'слабая' if abs(sc) >= 1 else 'нет'
    ctx['score'] = sc; ctx['conf'] = conf
    ctx.update(swing=sw, sub=sb, rec=rec)
    return ctx


def _liq_w(name):
    return 2.0 if 'D1' in name else 1.5 if ('вчера' in name or 'Лондон' in name) else 1.0


def struct_line(ctx, price, liq, fm):
    """«Где цена» (04.10.2026): Swing + откат % + Sub; до слома (<70% рано / >=70% близко); CHoCH если был; цель-ликвидность.
    Рекомендацию и вероятность не дублируем — они в блоке «Рекомендация»."""
    sw, sb = ctx['swing'], ctx['sub']
    nf = lambda v: ('%.5f' % v) if v < 20 else ('%.2f' % v)
    hi, lo, tr = sw.get('hi'), sw.get('lo'), sw['tr']
    parts = []
    r = None
    if hi and lo and hi > lo and tr != 0:
        rng = hi - lo
        arrow = lambda t: '▲' if t == 1 else '▼'
        if tr == -1:
            r = (price - lo) / rng
            base = ('Swing ▼: импульс вниз, цена у LL %s' % nf(lo)) if r <= 0.1 else \
                   ('Swing ▼: откат %d%% вверх от LL %s к LH %s' % (round(r * 100), nf(lo), nf(hi)))
            brk_lvl = 'выше LH %s' % nf(hi)
        else:
            r = (hi - price) / rng
            base = ('Swing ▲: импульс вверх, цена у HH %s' % nf(hi)) if r <= 0.1 else \
                   ('Swing ▲: откат %d%% вниз от HH %s к HL %s' % (round(r * 100), nf(hi), nf(lo)))
            brk_lvl = 'ниже HL %s' % nf(lo)
        if sb['tr'] == -tr: base += ' · Sub M15 %s против Swing' % arrow(sb['tr'])
        elif sb['tr'] == tr: base += ' · Sub M15 %s по тренду' % arrow(sb['tr'])
        parts.append(base)
        if sb['tr'] == -tr or r > 0.1:
            if r >= 0.7 or sw.get('deep'): parts.append('Откат 70%%+: слом близко, смотрим закрытие телом %s' % brk_lvl)
            elif sb['tr'] == -tr: parts.append('Откат меньше 70%%: о сломе рано, слом = закрытие телом %s' % brk_lvl)
        for nm, t in (('Swing', sw), ('Sub M15', sb)):
            if t.get('brk'):
                parts.append('CHoCH %s: %s' % (nm, t['brk'].replace('закрытие телом за', 'телом за')))
    else:
        parts.append('Swing: чёткого тренда нет, цена в диапазоне')
    # цель-ликвидность: ближайший неснятый уровень (расстояние в длинах ноги Swing / вес силы уровня)
    if liq:
        rng = max((hi - lo) if (hi and lo and hi > lo) else price * 0.005, 1e-9)
        cand = []
        for x in liq:
            d = abs(x['p'] - price) / rng
            if d > 2.5: continue
            against = tr != 0 and ((x['p'] > price and tr == -1) or (x['p'] < price and tr == 1)) and sb['tr'] == -tr
            cand.append((d / (_liq_w(x['name']) * (1.5 if against else 1.0)), x, d))
        cand.sort(key=lambda c: c[0])
        if cand:
            def fmtl(c): return '%s %s %s' % ('↑' if c[1]['p'] > price else '↓', nf(c[1]['p']), c[1]['name'])
            txt = 'Цель-ликвидность: ' + fmtl(cand[0]) + ' (%.1f ноги)' % cand[0][2]
            if len(cand) > 1: txt += ' · следом ' + fmtl(cand[1])
            parts.append(txt)
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
