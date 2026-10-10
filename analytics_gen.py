"""Аналитика сделок для Пульта (11.10.2026): записи для вкладки «Аналитика сделок», карточек и истории.

Хранится state/analytics.json = {"A": [...], "C": [...]} — только последние KEEP (=10) сделок по каждому типу:
новая сделка добавляется, самая старая удаляется. Запись содержит всё, что нужно графику: M5 за день,
H1 за 7 суток, неинвертированные H1 FVG, неснятую ликвидность, бокс, экстремум выноса, уровни сделки.

Два входа:
  add_closed(sym, window, r, off, date_str) — вызывается тиком, когда сделка закрылась (TP/SL/БУ/22:00);
  replay(typ, D, last_day, need)           — повтор движком на истории (для первичного наполнения).
"""
import os, re, json, datetime as dt
import pandas as pd

import pult_rules as PR
import pult_s1 as S1
import pult_ctx as X

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, 'state', 'analytics.json')
KEEP = 10
DEC = PR.DEC
RR = {'A': 2.0, 'C': 3.0}


def _dec(s): return DEC.get(s, 5)


def _outcome_from_note(note):
    nt = note or ''
    if '→ TP' in nt or 'TP' in nt and 'ЗАКРЫТА' in nt: return 'TP'
    if '→ SL' in nt or 'SL' in nt and 'ЗАКРЫТА' in nt: return 'SL'
    if '→ БУ' in nt or 'БУ' in nt and 'ЗАКРЫТА' in nt: return 'BE'
    return 'T22'


def _simulate(bars, typ, sig, out):
    """Время и R выхода по барам (метки Рига). Вход — открытие бара tin, проверка со следующего бара.
    Внутри одного бара стоп считается раньше цели (консервативно, как в движке)."""
    sd = 1 if sig['side'] == 'long' else -1
    e, st, tp = float(sig['entry']), float(sig['stop']), float(sig['tp'])
    be = sig.get('be_at')
    risk = abs(e - st) or 1e-9
    idx = next((i for i, b in enumerate(bars) if b[4] == sig['time']), None)
    if idx is None: return None, None
    cur = st; armed = False
    for b in bars[idx + 1:]:
        hi, lo = b[1], b[2]
        hit_stop = lo <= cur if sd == 1 else hi >= cur
        hit_tp = hi >= tp if sd == 1 else lo <= tp
        if hit_stop:
            return b[4], (0.0 if armed else -1.0)
        if hit_tp:
            return b[4], RR[typ]
        if typ == 'C' and be and not armed and ((hi >= be) if sd == 1 else (lo <= be)):
            armed = True; cur = e
    last = bars[-1]
    return '22:00', round(sd * (last[3] - e) / risk, 2)


def _context(s, day, o, df, tin_utc, typ):
    """FVG, ликвидность, H1-бары на момент входа (без заглядывания вперёд)."""
    dec = _dec(s)
    cut = tin_utc + pd.Timedelta(minutes=5)
    dc = df[(df.index < cut) & (df.index >= cut - pd.Timedelta(days=12))]
    h1c = S1.h1_from_m5(df[(df.index < cut) & (df.index >= cut - pd.Timedelta(days=40))])
    h1c = h1c[h1c.index + pd.Timedelta(hours=1) <= cut]
    F1, _atr1 = PR._h1_fvgs(h1c)
    fv = []
    for f in F1:
        if f['inv_t'] is None:
            t0 = pd.Timestamp(f['t']) - pd.Timedelta(hours=1)
            fv.append([str((t0 + pd.Timedelta(hours=o)).strftime('%Y-%m-%d %H:%M')), round(f['lo'], dec), round(f['hi'], dec), f['dir']])
    loc = dc.index + pd.Timedelta(hours=o)
    dl = dc.copy(); dl['rdate'] = [x.date() for x in loc]; dl['rmin'] = [x.hour * 60 + x.minute for x in loc]
    liq = X.liquidity(h1c, dl, day, o, float(dc['Close'].iloc[-1]))
    lq = []
    for q in liq:
        nm = q['name']; m = re.search(r'(\d\d)\.(\d\d)(?: (\d\d):(\d\d))?$', nm)
        if m:
            dd_, mm_ = int(m.group(1)), int(m.group(2)); yy = day.year if mm_ <= day.month else day.year - 1
            ts = f'{yy}-{mm_:02d}-{dd_:02d} {m.group(3) or "00"}:{m.group(4) or "00"}'
        else:
            pd_ = day - dt.timedelta(days=1)
            while pd_.weekday() >= 5: pd_ -= dt.timedelta(days=1)
            ts = f'{pd_} ' + ('11:00' if 'Лондон' in nm and typ == 'C' else '00:00')
        lq.append([round(q['p'], dec), q['kind'], ts, nm])
    hh = h1c[h1c.index >= cut - pd.Timedelta(days=7)]
    h1b = [[float(r_.Open), float(r_.High), float(r_.Low), float(r_.Close), (t + pd.Timedelta(hours=o)).strftime('%Y-%m-%d %H:%M')] for t, r_ in hh.iterrows()]
    return fv, lq, h1b


def _day_bars(df, day, o, typ, end_utc):
    h0, m0 = (2, 30) if typ == 'A' else (10, 30)
    lo_ = pd.Timestamp(dt.datetime.combine(day, dt.time(h0, m0)) - dt.timedelta(hours=o), tz='UTC')
    dd = df[(df.index >= lo_) & (df.index < end_utc)]
    return [[float(r_.Open), float(r_.High), float(r_.Low), float(r_.Close), (t + pd.Timedelta(hours=o)).strftime('%H:%M')] for t, r_ in dd.iterrows()]


def build(typ, s, day, o, df, sig, boxH, boxL, ext, out, R=None, xt=None, end_utc=None):
    """Одна запись аналитики. df — M5 (индекс UTC, tz-aware), sig — сигнал движка, out ∈ TP/SL/BE/T22."""
    tin = pd.Timestamp(sig['t_utc'])
    if tin.tzinfo is None: tin = tin.tz_localize('UTC')
    if end_utc is None:
        end_utc = pd.Timestamp(dt.datetime.combine(day, dt.time(22, 5)) - dt.timedelta(hours=o), tz='UTC')
    bars = _day_bars(df, day, o, typ, end_utc)
    if R is None or xt is None:
        xt2, R2 = _simulate(bars, typ, sig, out)
        xt = xt or xt2 or '22:00'
        if R is None:
            R = {'TP': RR[typ], 'SL': -1.0, 'BE': 0.0}.get(out, R2 if R2 is not None else 0.0)
    fv, lq, h1b = _context(s, day, o, df, tin, typ)
    rec = dict(id=f'{typ}_{s}_{day}', sym=s, typ=typ, day=str(day), boxH=boxH, boxL=boxL, ext=ext, side=sig['side'], entry=sig['entry'],
               stop=sig['stop'], tp=sig['tp'], tin=sig['time'], res=out, R=round(float(R), 2), xt=xt,
               bars=bars, h1=h1b, fvg=fv, liq=lq, prob=sig.get('prob'), struct=sig.get('struct'))
    if typ == 'A':
        rec['liqx'] = sig.get('liqx'); rec['swn'] = sig.get('swn')
    else:
        rec['be'] = sig.get('be_at')
        i = next((k for k, b in enumerate(bars) if b[4] == sig['time']), None)
        if i:
            seg = bars[max(0, i - 14):i]
            a = sum(x[1] - x[2] for x in seg) / len(seg)
            rec['atr'] = a
            rec['rk'] = round(abs(sig['entry'] - sig['stop']) / a, 2) if a else None
    return rec


# ---------- хранилище: последние KEEP по каждому типу ----------
def load(path=PATH):
    try:
        with open(path, encoding='utf-8') as f:
            j = json.load(f)
        return {'A': list(j.get('A') or []), 'C': list(j.get('C') or [])}
    except Exception:
        return {'A': [], 'C': []}


def upsert(rec, path=PATH, keep=KEEP):
    j = load(path)
    L = [x for x in j[rec['typ']] if x['id'] != rec['id']]
    L.append(rec)
    L.sort(key=lambda x: (x['day'], x['tin'], x['sym']))
    j[rec['typ']] = L[-keep:]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(j, f, ensure_ascii=False, separators=(',', ':'))
    return j


# ---------- вход из тика ----------
def has(typ, sym, date_str, path=PATH):
    i = f'{typ}_{sym}_{date_str}'
    return any(x['id'] == i for x in load(path)[typ])


def add_closed(sym, window, r, off, date_str, force=False):
    """Вызывается тиком после закрытия сделки (там же, где рисуются скриншоты). force=True — перезаписать запись
    (в 22:05 бары добираются до конца дня)."""
    import live_check as lc
    sig = r.get('signal') or {}
    if not sig.get('t_utc'): return None
    if not force and has(window, sym, date_str): return None
    d = lc.fetch(lc.ticker_for(sym, window), sig.get('src', 'Yahoo'))
    if d is None or len(d) < 50: return None
    d = d[['Open', 'High', 'Low', 'Close']].dropna()
    if d.index.tz is None: d.index = d.index.tz_localize('UTC')
    day = dt.date.fromisoformat(date_str)
    out = _outcome_from_note(r.get('note'))
    ext = r.get('extreme')
    R = r.get('exit_r') if out == 'T22' else None
    rec = build(window, sym, day, off, d, sig, r.get('boxH'), r.get('boxL'), ext, out, R=R)
    if rec['ext'] is None: rec['ext'] = rec['stop']
    upsert(rec)
    return rec['id']


# ---------- повтор движком на истории (первичное наполнение и проверка) ----------
def _utc_off(day):
    from zoneinfo import ZoneInfo
    return int(pd.Timestamp(dt.datetime.combine(day, dt.time(12))).tz_localize(ZoneInfo('Europe/Riga')).utcoffset().total_seconds() // 3600)


def replay(typ, D, last_day, need, log=print, max_back=400):
    """D = {sym: M5 DataFrame (UTC)}; идём от last_day назад, пока не наберём need сделок.
    Каждый сигнал проверяется на моменте входа (+10 мин) — как в реальном времени."""
    res = []; day = last_day; tried = 0
    t_end = (14, 5) if typ == 'A' else (18, 35)
    analyze = PR._analyze_A_s1 if typ == 'A' else PR._analyze_C2
    while len(res) < need and tried < max_back:
        tried += 1
        if day.weekday() < 5:
            o = _utc_off(day)
            for s, df in D.items():
                now1 = pd.Timestamp(dt.datetime.combine(day, dt.time(*t_end)) - dt.timedelta(hours=o), tz='UTC')
                now2 = pd.Timestamp(dt.datetime.combine(day, dt.time(22, 5)) - dt.timedelta(hours=o), tz='UTC')
                d1 = df[(df.index < now1) & (df.index >= now1 - pd.Timedelta(days=12))]
                if len(d1) < 100 or d1.index[-1] < now1 - pd.Timedelta(minutes=30): continue
                h1 = S1.h1_from_m5(df[(df.index < now1) & (df.index >= now1 - pd.Timedelta(days=40))])
                try: r = analyze(s, d1, now1.tz_localize(None).to_pydatetime(), o, {}, h1)
                except Exception as e: log('ERR', s, day, e); continue
                sig = r.get('signal')
                if not sig: continue
                nowc = pd.Timestamp(sig['t_utc']) + pd.Timedelta(minutes=10)
                dcz = df[(df.index < nowc) & (df.index >= nowc - pd.Timedelta(days=12))]
                h1z = S1.h1_from_m5(df[(df.index < nowc) & (df.index >= nowc - pd.Timedelta(days=40))])
                try: rz = analyze(s, dcz, nowc.tz_localize(None).to_pydatetime(), o, {}, h1z)
                except Exception as e: log('ERRZ', s, day, e); continue
                if not (rz.get('signal') and rz['signal']['time'] == sig['time']):
                    log('SKIP-CAUSAL', s, day, sig['time']); continue
                d2 = df[(df.index < now2) & (df.index >= now2 - pd.Timedelta(days=12))]
                r2 = analyze(s, d2, now2.tz_localize(None).to_pydatetime(), o, {'signal': sig}, h1)
                tg = r2.get('tg_note') or ''
                out = 'TP' if 'TP' in tg else 'SL' if 'SL' in tg else 'BE' if 'БУ' in tg else 'T22' if '22' in tg else 'OPEN'
                R = {'TP': RR[typ], 'SL': -1.0, 'BE': 0.0}.get(out, r2.get('exit_r', 0.0))
                xt = r2.get('exit_time') or '22:00'
                rec = build(typ, s, day, o, df, sig, r['boxH'], r['boxL'], r.get('extreme'), out, R, xt, end_utc=now2)
                res.append(rec)
                log('TRADE', typ, s, day, sig['side'], sig['time'], sig['entry'], out, R, xt)
        day -= dt.timedelta(days=1)
    res.sort(key=lambda x: (x['day'], x['tin'], x['sym']))
    return res[-need:] if len(res) > need else res
