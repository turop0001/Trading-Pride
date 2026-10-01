"""Скриншоты сделки (M5 за день и H1 за 5 дней) для карточек Пульта — 29.09.2026.

Рисуются один раз, когда сигнал закрылся (TP или SL), сохраняются в state/shots/ и
коммитятся вместе с состоянием; Пульт и страница подписчиков показывают их прямо в карточке.
"""
import os
import datetime as dt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

import live_check as lc

SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'shots')
UP, DN = '#26a69a', '#ef5350'
C_ENTRY, C_STOP, C_TP = '#2962ff', '#d32f2f', '#2e7d32'
C_PREV = '#9e9e9e'
# цвета сессий как на графике трейдера: Азия — жёлтая, Лондон — синий, Нью-Йорк — фиолетовый
SESS = (('Азия', 3.0, 10.0, '#fff3b0', '#8a6d00'), ('Лондон', 11.0, 16 + 25 / 60, '#dbe7fb', '#2f5f9e'), ('Нью-Йорк', 16.5, 18.5, '#eadcf7', '#6b3fa0'))


def _sessions(ax, d, off, alpha, label):
    for dd in sorted({i.normalize() for i in d.index}):
        for name, h0, h1, fc, tc in SESS:
            a0 = dd + pd.Timedelta(hours=h0 - off); a1 = dd + pd.Timedelta(hours=h1 - off)
            seg = d[(d.index >= a0) & (d.index < a1)]
            if len(seg) < 2: continue
            i0 = int((d.index >= a0).argmax())
            lo, hi = seg['Low'].min(), seg['High'].max()
            ax.add_patch(Rectangle((i0 - 0.5, lo), len(seg), hi - lo, color=fc, alpha=alpha, zorder=1))
            if label:
                ax.text(i0, hi, ' ' + name, fontsize=9, va='bottom', color=tc, fontweight='bold')


def _fvg_liq(ax, h, t_in):
    """H1 FVG (непробитые до входа) полосами и непробитая ликвидность кружками."""
    from matplotlib.lines import Line2D
    pre = h[h.index <= t_in]
    n = len(pre)
    H, L, C = pre['High'].values, pre['Low'].values, pre['Close'].values
    atr = float((pre['High'] - pre['Low']).iloc[-48:].mean()) if n > 5 else 0
    for i in range(2, n):
        if L[i] > H[i - 2] and L[i] - H[i - 2] >= 0.15 * atr:      # бычий FVG
            lo, hi, bull = H[i - 2], L[i], True
        elif H[i] < L[i - 2] and L[i - 2] - H[i] >= 0.15 * atr:    # медвежий FVG
            lo, hi, bull = H[i], L[i - 2], False
        else:
            continue
        after = C[i + 1:]
        if len(after) and ((after < lo).any() if bull else (after > hi).any()):
            continue                                                # пробит телом — не рисуем
        ax.add_patch(Rectangle((i - 2.5, lo), len(h) - i + 2, hi - lo,
                               color='#26a69a' if bull else '#ef5350', alpha=0.13, zorder=0.5))
    for i in range(2, n - 2):
        if H[i] >= max(H[i - 2:i + 3]) and not (pre['High'].values[i + 1:] > H[i]).any():
            ax.scatter([i], [H[i]], s=260, facecolors='none', edgecolors='#7b3fa0', linewidths=1.8, zorder=5)
        if L[i] <= min(L[i - 2:i + 3]) and not (pre['Low'].values[i + 1:] < L[i]).any():
            ax.scatter([i], [L[i]], s=260, facecolors='none', edgecolors='#1f6aa5', linewidths=1.8, zorder=5)
    ax.legend(handles=[
        Line2D([], [], marker='o', ls='', mfc='none', mec='#7b3fa0', ms=11, mew=1.8, label='непробитая ликвидность сверху (хай)'),
        Line2D([], [], marker='o', ls='', mfc='none', mec='#1f6aa5', ms=11, mew=1.8, label='непробитая ликвидность снизу (лоу)'),
        Rectangle((0, 0), 1, 1, color='#26a69a', alpha=0.25, label='H1 FVG лонговый (непробитый)'),
        Rectangle((0, 0), 1, 1, color='#ef5350', alpha=0.25, label='H1 FVG шортовый (непробитый)'),
    ], loc='upper left', fontsize=8, framealpha=0.9)


def _candles(ax, d, width):
    xs = range(len(d))
    for i, (_, r) in zip(xs, d.iterrows()):
        c = UP if r['Close'] >= r['Open'] else DN
        ax.vlines(i, r['Low'], r['High'], color=c, linewidth=0.8, zorder=2)
        lo, hi = sorted((r['Open'], r['Close']))
        ax.add_patch(Rectangle((i - width / 2, lo), width, max(hi - lo, 1e-9), color=c, zorder=3))


def _xticks(ax, d, off, fmt, n=8):
    step = max(1, len(d) // n)
    idx = list(range(0, len(d), step))
    ax.set_xticks(idx)
    ax.set_xticklabels([(d.index[i] + pd.Timedelta(hours=off)).strftime(fmt) for i in idx], rotation=35, ha='right', fontsize=8)


def _levels(ax, n, sig, dec, ie=None):
    for y, c, t in ((sig['entry'], C_ENTRY, 'ВХОД'), (sig['stop'], C_STOP, 'СТОП'), (sig['tp'], C_TP, 'ТЕЙК %gR' % float(sig.get('rr') or 2))):
        ax.axhline(y, color=c, linewidth=1.4 if t != 'ВХОД' else 1.0, linestyle='-' if t != 'ВХОД' else '--', zorder=4)
        if t == 'ВХОД' and ie is not None:
            x, ha = min(ie + max(6, int(n * 0.07)), n - 1), 'left'      # правее точки входа, чтобы не закрывать её
        else:
            x, ha = n - 1, 'right'
        ax.annotate(f'{t} {y:.{dec}f}', (x, y), xytext=(0, 4), textcoords='offset points', ha=ha, va='bottom',
                    color=c, fontsize=10, fontweight='bold', zorder=7,
                    bbox=dict(boxstyle='round,pad=0.25', fc='white', ec=c, lw=0.8, alpha=0.95))


def _foot(fig, r):
    """Подпись под графиком: вероятность, выполненные пункты, ухудшители, разбор SL (01.10.2026)."""
    sg = r.get('signal') or {}
    parts = []
    if sg.get('prob'): parts.append('Вероятность: ' + sg['prob'])
    if sg.get('ck'): parts.append('выполнено пунктов: ' + ', '.join(str(x) for x in sg['ck']))
    if sg.get('plus'): parts.append('усилители №' + ', '.join(str(x) for x in sg['plus']))
    if sg.get('worse'): parts.append('ухудшитель №' + ', '.join(str(x) for x in sg['worse']))
    st = (r.get('struct') or {})
    if st.get('rec'): parts.append('структура: ' + st['rec'] + f" (Swing {st.get('swing', '')}, Sub {st.get('sub', '')})")
    txt = ' · '.join(parts)
    if r.get('sl_why'): txt += '\n' + r['sl_why']
    if txt:
        fig.text(0.01, 0.005, txt, fontsize=8.5, color='#b71c1c' if r.get('sl_why') else '#444', va='bottom', wrap=True)


def _style(fig, ax, title, subtitle):
    ax.set_title(title, fontsize=12, fontweight='bold', loc='left', pad=18)
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=9, color='#555')
    ax.grid(True, color='#eee', linewidth=0.6)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.yaxis.tick_right()
    fig.tight_layout(rect=(0, 0.06, 1, 1))


def make_shots(sym, window, r, off, date_str):
    """Возвращает {'m5': relpath, 'h1': relpath} или None."""
    sig = r.get('signal') or {}
    if not sig.get('t_utc'):
        return None
    ticker = lc.ticker_for(sym, window)
    d = lc.fetch(ticker, sig.get('src', 'Yahoo'))
    if d is None or len(d) < 50:
        return None
    d = d[['Open', 'High', 'Low', 'Close']].dropna()
    dec = 2 if sym in ('XAUUSD',) else (1 if sym in ('US500', 'NAS100', 'US30', 'GER40') else 5)
    t_in = pd.Timestamp(sig['t_utc'])
    if t_in.tzinfo is None:
        t_in = t_in.tz_localize('UTC')
    if d.index.tz is None:
        d.index = d.index.tz_localize('UTC')
    day = pd.Timestamp(date_str).tz_localize('UTC')
    side = 'LONG' if sig.get('side') == 'long' or sig['tp'] > sig['entry'] else 'SHORT'
    nt_ = r.get('note') or ''
    res = 'TP' if 'TP' in nt_ else ('БУ' if 'БУ' in nt_ else ('22:00' if '22:00' in nt_ else 'SL'))
    os.makedirs(SHOT_DIR, exist_ok=True)
    base = f"{date_str}_{sym}_{window}"
    out = {}

    # ---- M5: день от начала бокса до закрытия сделки + 1 час
    b0 = day + pd.Timedelta(hours=3 - off)
    m = d[(d.index >= b0 - pd.Timedelta(minutes=30)) & (d.index <= day + pd.Timedelta(hours=20 - off))]
    if len(m) > 20:
        fig, ax = plt.subplots(figsize=(13, 6.2), dpi=110)
        _candles(ax, m, 0.6)
        _sessions(ax, m, off, 0.6, True)
        if window == 'A' and r.get('prevL') is not None:
            for y in (r['prevL'], r['prevH']):
                ax.axhline(y, color=C_PREV, linestyle=':', linewidth=1, zorder=1)
            ax.text(0, r['prevH'], ' вчерашний бокс', fontsize=8, color=C_PREV, va='bottom')
        ie = int((m.index <= t_in).sum()) - 1
        ax.scatter([ie], [sig['entry']], marker='^' if side == 'LONG' else 'v', s=140, color=C_ENTRY, zorder=6, edgecolor='white')
        ax.annotate(f"вход {sig['time']}", (ie, sig['entry']), textcoords='offset points', xytext=(14, -20 if side == 'LONG' else 16),
                    fontsize=9, color=C_ENTRY, fontweight='bold')
        _levels(ax, len(m), sig, dec, ie)
        _xticks(ax, m, off, '%H:%M')
        if window == 'C' and r.get('boxH') is not None:
            for y_ in (r['boxL'], r['boxH']): ax.axhline(y_, color='#2f5f9e', linestyle=':', linewidth=1, zorder=1)
            ax.text(0, r['boxH'], ' бокс Лондона', fontsize=8, color='#2f5f9e', va='bottom')
        if sig.get('be_at'): ax.axhline(sig['be_at'], color='#f9a825', linestyle='--', linewidth=1, zorder=4); ax.annotate(f"БУ при {sig['be_at']:.{dec}f}", (len(m) - 1, sig['be_at']), ha='right', fontsize=9, color='#f9a825')
        _style(fig, ax, f"{sym} · тип {window} · {side} · {res}", f"M5 · {pd.Timestamp(date_str).strftime('%d.%m.%Y')} · Азия жёлтая, Лондон синий, Нью-Йорк фиолетовый · время Рига")
        _foot(fig, r)
        p = os.path.join(SHOT_DIR, base + '_m5.png'); fig.savefig(p); plt.close(fig)
        out['m5'] = 'state/shots/' + base + '_m5.png'

    # ---- H1: 5 дней до входа + остаток дня
    h = d.resample('1h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    h = h[(h.index >= day - pd.Timedelta(days=5)) & (h.index <= day + pd.Timedelta(hours=21 - off))]
    if len(h) > 20:
        fig, ax = plt.subplots(figsize=(13, 6.2), dpi=110)
        _candles(ax, h, 0.62)
        _sessions(ax, h, off, 0.45, False)
        _fvg_liq(ax, h, t_in)
        ie = int((h.index <= t_in).sum()) - 1
        ax.scatter([ie], [sig['entry']], marker='^' if side == 'LONG' else 'v', s=140, color=C_ENTRY, zorder=6, edgecolor='white')
        _levels(ax, len(h), sig, dec, ie)
        _xticks(ax, h, off, '%d.%m %H:%M', n=10)
        _style(fig, ax, f"{sym} · тип {window} · {side} · {res}", "H1 · 5 дней до входа · Азия жёлтая, Лондон синий, Нью-Йорк фиолетовый · время Рига")
        _foot(fig, r)
        p = os.path.join(SHOT_DIR, base + '_h1.png'); fig.savefig(p); plt.close(fig)
        out['h1'] = 'state/shots/' + base + '_h1.png'
    return out or None
