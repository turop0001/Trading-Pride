#!/usr/bin/env python3
"""Облачный чек Пульта — без браузера и без компьютера пользователя.
Данные: yfinance. ЧЕСТНЫЕ ОГРАНИЧЕНИЯ (проверено 26.09.2026):
  - задержка обычно 5-20 минут для форекс/индексов/золота против реалтайма TradingView;
  - XAUUSD идёт через PAXG-USD (токенизированное золото на крипторынке, 24/7) —
    расхождение со спотом OANDA:XAUUSD на TradingView ~2-3$ (было ~35.5$ при фьючерсе GC=F);
  - US500/NAS100 остаются на фьючерсах ES=F/NQ=F (проверил кэш-индексы ^GSPC/^NDX как
    альтернативу — не годится: они не торгуются в период самого бокса, см. комментарий
    у TICKERS_WINDOW_C_OVERRIDE);
  - EURUSD/GBPUSD/USDJPY/EURGBP через yfinance "=X" — синтетическая индикативная квота, не поток
    конкретного брокера; в тонкие часы (вечер/выходные) бывают ЗАСТЫВШИЕ бары (одна и та же цена
    несколько баров подряд) — это НЕ означает "рынок стоит", это означает "нет свежих данных";
    скрипт помечает такие случаи как 'stale' и не шлёт по ним ложных сигналов.
Логика: упрощённая версия правил Пульта (снятие бокса), достаточная для сигнала "статус
изменился, посмотри на график", а не для точного бэктеста (нет H1 FVG/CHoCH/ликвидности).

ИСПРАВЛЕНО 26.09.2026 (вечер): границы боксов уточнены пользователем — бокс Азии
03:00-10:00 Рига (было приблизительно 00:00-10:05), бокс Лондона 11:00-16:25 Рига
(было приблизительно 10:05-16:30). Тот же баг (границы не по факту Риги) был найден и
в механическом скринере scan.py — см. его комментарии; часть статистических правил
Пульта (модель «контр-bias», усилитель «снят Франкфурт») пересчитана и изменена.
"""
import json, os, sys, datetime as dt
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notify import send_telegram, fmt_line, build_update, DIR_LONG, DIR_SHORT

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'pult_state.json')

# ИСПРАВЛЕНО 28.09.2026 (проверка готовности перед стартом торгового дня): TICKERS отставал
# от актуального списка инструментов (см. трейдинг/продолжение-26-09-2026.md, п.7) — держал
# USDJPY/EURGBP (исключены из ОБЕИХ моделей ещё 27.09.2026) и не имел US30/GER40 вовсе.
# USDJPY/EURGBP убраны. US30 добавлен (YM=F, фьючерс CME, торгуется непрерывно как ES=F/NQ=F —
# тикер проверен вручную 28.09.2026, данные приходят). GER40 пока НЕ добавлен: единственный
# найденный тикер DAX на yfinance — кэш-индекс ^GDAXI, который не торгуется в часы бокса Азии
# (03:00-10:00 Рига = 02:00-09:00 CET, до открытия Xetra) — та же проблема, что раньше отклонили
# для US500/NAS100 (см. комментарий ниже про TICKERS_WINDOW_C_OVERRIDE); нужен отдельный
# continuously-traded прокси (как PAXG-USD для золота), не найден за время этой проверки —
# GER40 остаётся ОТКРЫТЫМ пробелом автоматики, проверять вручную до дальнейшего решения.
TICKERS = {
    'XAUUSD': 'PAXG-USD', 'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X',
    'US500': 'ES=F', 'NAS100': 'NQ=F', 'US30': 'YM=F', 'GER40': 'MT5:GER40',
}

# Инструменты по типу — Тип A торгует все 7 (GER40 временно пропущен, см. комментарий выше),
# Тип C только 3 (XAUUSD/EURUSD/GBPUSD) — раньше main() проверял ВСЕ TICKERS в обоих окнах.
WINDOW_SYMBOLS = {
    'A': ['XAUUSD', 'EURUSD', 'GBPUSD', 'US500', 'NAS100', 'US30', 'GER40'],
    'C': ['XAUUSD', 'EURUSD', 'GBPUSD'],
}

# ПРОВЕРЕНО 26.09.2026: замена GC=F -> PAXG-USD резко снижает разницу со спотом
# (крипто-токен привязан к физическому золоту, торгуется 24/7): было ~35.5$ (0.83%)
# от TradingView OANDA:XAUUSD, стало ~2-3$. Альтернатива XAUT-USD даёт похожий результат.
#
# ПРОВЕРЕНО И ОТКЛОНЕНО: пробовал для US500/NAS100 переключать на кэш-индексы (^GSPC/^NDX)
# в окне C — не работает: сам бокс окна C считается по периоду 10:05-16:30 Рига (сессия
# Лондона), а кэш-индекс в это время ЕЩЁ НЕ ТОРГУЕТСЯ (NYSE открывается только в 16:30 Рига) —
# получается no_box. А смешивать источник бокса (фьючерс) с источником цены (кэш-индекс) —
# то самое смешивание источников, которое вносит новую неточность вместо старой.
# Поэтому US500/NAS100 остаются на фьючерсах ES=F/NQ=F в обоих окнах — это единственный
# источник, который непрерывно торгуется в течение всего периода бокса и после.
TICKERS_WINDOW_C_OVERRIDE = {}


def ticker_for(sym, window):
    if window == 'C' and sym in TICKERS_WINDOW_C_OVERRIDE:
        return TICKERS_WINDOW_C_OVERRIDE[sym]
    return TICKERS[sym]


def riga_now():
    now_utc = dt.datetime.utcnow()
    y = now_utc.year
    def lastsun(m):
        x = dt.date(y, m, 31)
        while x.weekday() != 6: x -= dt.timedelta(1)
        return x
    bst = lastsun(3) <= now_utc.date() < lastsun(10)
    off = 3 if bst else 2
    return now_utc + dt.timedelta(hours=off), off


C_ENABLED = True    # 01.10.2026: Тип C снова включён (новые правила, бокс Лондона 11:00–16:25, вход 16:30–18:30)


def window_now(riga_dt):
    mins = riga_dt.hour * 60 + riga_dt.minute
    if 600 <= mins < 840: return 'A'   # 10:00-14:00
    if C_ENABLED and 990 <= mins < 1110: return 'C'  # 16:30-18:30
    return None


# ДОБАВЛЕНО 28.09.2026 (вечер, по просьбе пользователя): нарратив тренда H1(7 суток)/D1(14
# суток) — раньше считался вручную через TradingView-браузер (tools/tv_narrative.js на Маке,
# ratio = net/средний_суточный_диапазон, лонг ≥+1.0/+1.5, шорт ≤−1.0/−1.5, иначе флэт),
# теперь то же самое считается прямо на облачных данных yfinance — не зависит от браузера.
# Только справочный контекст (усилитель из чек-листа "Тренд 5 дней"), не фильтр входа.
def _fill_asia_gap(m, ticker, period):
    """02.10.2026: Yahoo подмешиваем ТОЛЬКО если в MT5 не хватает свечей бокса Азии сегодня (<60 из ~84) —
    например, терминал был выключен ночью. Обычная часовая пауза индексов дыру не создаёт и ничего не подмешивает:
    иначе уровни фьючерса Yahoo смешиваются с ценами CFD брокера (ложные/запоздалые сигналы)."""
    import pandas as pd
    if m is None or str(ticker).startswith('MT5:'): return m
    try:
        riga, off = riga_now()
        if riga.hour * 60 + riga.minute < 600 or riga.weekday() >= 5: return m   # бокс Азии ещё идёт / выходной
        loc = m.index + pd.Timedelta(hours=off)
        today = riga.date()
        n = int(sum(1 for x in loc if x.date() == today and 180 <= x.hour * 60 + x.minute < 600))
        if n >= 60: return m
        import yfinance as yf
        y = yf.download(ticker, period=period, interval='5m', progress=False, auto_adjust=False)
        if y is None or len(y) == 0: return m
        if isinstance(y.columns, pd.MultiIndex): y.columns = y.columns.get_level_values(0)
        y = y.tz_localize('UTC') if y.index.tz is None else y.tz_convert('UTC')
        return m.combine_first(y[['Open', 'High', 'Low', 'Close']]).sort_index()
    except Exception:
        return m


def fetch_ohlc(ticker, period, interval):
    m = mt5_frame(ticker, {'60m': 'H1', '1d': 'D1'}.get(interval, 'M5'), max_age_h={'60m': 2, '1d': 72}.get(interval, 72))   # 02.10.2026: H1 из фида не старше ~3 ч (раньше 72 ч → при выключенном MT5 H1 отставал на сутки, а M5 шёл из Yahoo)
    if m is not None and len(m) >= 10 and interval not in ('60m', '1d'):
        m = _fill_asia_gap(m, ticker, period)
    if m is not None and len(m) >= 10: return m
    if str(ticker).startswith('MT5:'): return None
    import yfinance as yf
    import pandas as pd
    d = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
    if d is None or len(d) == 0: return None
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.tz_localize('UTC') if d.index.tz is None else d.tz_convert('UTC')
    return d


def trend(ticker, period, interval, days, thr):
    import pandas as pd
    d = fetch_ohlc(ticker, period, interval)
    if d is None or len(d) < 10: return {'tr': 'нет данных'}
    frm = d.index[-1] - pd.Timedelta(days=days)
    w = d[d.index >= frm]
    if len(w) < 5: return {'tr': 'нет данных'}
    dly = w.groupby(w.index.date).agg(h=('High', 'max'), l=('Low', 'min'))
    avg = float((dly['h'] - dly['l']).mean())
    net = float(w['Close'].iloc[-1] - w['Open'].iloc[0])
    ratio = net / avg if avg else 0
    tr = 'лонг' if ratio >= thr else 'шорт' if ratio <= -thr else 'боковик'
    pct = round(net / float(w['Open'].iloc[0]) * 10000) / 100
    return {'tr': tr, 'ratio': round(ratio, 2), 'pct': pct}


def trend_narrative(ticker):
    """Возвращает {'h1': {...}, 'd1': {...}} или None, если тикер не поддерживается (GER40)."""
    if not ticker: return None
    try:
        return {'h1': trend(ticker, '15d', '60m', 7, 1.0), 'd1': trend(ticker, '35d', '1d', 14, 1.5)}
    except Exception:
        return None


def fetch(ticker, src=None):
    # src='Yahoo' — принудительно Yahoo (сигнал был посчитан по Yahoo: уровни фьючерса ≠ цены CFD)
    m = None if src == 'Yahoo' else mt5_frame(ticker, 'M5')
    if m is not None:
        return _fill_asia_gap(m, ticker, '10d')
    if str(ticker).startswith('MT5:'): return None
    import yfinance as yf
    import pandas as pd
    # ИСПРАВЛЕНО 28.09.2026: period 5d -> 10d. Для вычисления bias нужен бокс ПРЕДЫДУЩЕГО
    # торгового дня (той же сессии) - в понедельник это прошлая пятница, т.е. до 3
    # календарных дней назад; 5d календарных дней от понедельника иногда не доставали
    # до пятницы. 10d с запасом покрывает любые выходные/праздники поблизости.
    d = yf.download(ticker, period='10d', interval='5m', progress=False, auto_adjust=False)
    if d is None or len(d) == 0: return None
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.tz_convert('UTC')
    return d


# 29.09.2026: ЦЕНЫ БРОКЕРА ИЗ MT5 вместо Yahoo. Советник PultBridge.mq5 (Tickmill) раз в минуту
# шлёт свечи M5/H1/D1 на сайт (/api/feed) -> ветка `feed`, файл feed/mt5.json. Если свежих свечей
# MT5 нет (терминал выключен) — прежний запасной путь Yahoo (кроме GER40: у Yahoo его нет).
FEED_URL = 'https://api.github.com/repos/turop0001/Trading-Pride/contents/feed/{}.json?ref=feed'
_FEED = {'t': 0, 'data': None}
SRC = {}   # sym -> 'MT5' | 'Yahoo' (для логов/карточек)


def _feed():
    import time, urllib.request
    if time.time() - _FEED['t'] < 15: return _FEED['data']
    _FEED['t'] = time.time()
    try:
        h = {'Accept': 'application/vnd.github.raw', 'User-Agent': 'pult'}
        tok = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if tok: h['Authorization'] = f'Bearer {tok}'
        parts = []
        for name in ('hist', 'live'):
            try:
                parts.append(json.load(urllib.request.urlopen(urllib.request.Request(FEED_URL.format(name), headers=h), timeout=20)))
            except Exception as e:
                print(f'MT5 feed {name} недоступен:', str(e)[:120])
        syms = {}
        for p in parts:   # live поверх hist: одинаковое время бара — берём более свежий
            for sym, tfs in (p.get('syms') or {}).items():
                for tf, bars in tfs.items():
                    m = syms.setdefault(sym, {}).setdefault(tf, {})
                    for b in bars: m[b[0]] = b
        _FEED['data'] = {'syms': {s: {tf: [m[k] for k in sorted(m)] for tf, m in t.items()} for s, t in syms.items()}} if syms else None
    except Exception as e:
        print('MT5 feed недоступен:', str(e)[:120]); _FEED['data'] = None
    return _FEED['data']


def _sym_of(ticker):
    t = str(ticker)
    if t.startswith('MT5:'): return t[4:]
    for k, v in TICKERS.items():
        if v == t: return k
    return None


def mt5_frame(ticker, tf='M5', max_age_h=None):
    """DataFrame (UTC, Open/High/Low/Close) из свечей MT5 или None, если данных нет / они несвежие."""
    import time
    import pandas as pd
    sym = _sym_of(ticker)
    data = _feed() if sym else None
    bars = (((data or {}).get('syms') or {}).get(sym) or {}).get(tf) or []
    if len(bars) < 10: return None
    if max_age_h is None:   # M5: в окне — не старше 20 мин, вне окна — 12 ч
        max_age_h = 20 / 60 if window_now(riga_now()[0]) else 12
    if time.time() - bars[-1][0] > max_age_h * 3600 + (86400 if tf == 'D1' else 3600 if tf == 'H1' else 300):
        return None
    d = pd.DataFrame(bars, columns=['t', 'Open', 'High', 'Low', 'Close'])
    d.index = pd.to_datetime(d.pop('t'), unit='s', utc=True)
    if tf == 'M5': SRC[sym] = 'MT5'
    return d


def is_stale(d, n=4):
    """Последние n баров с одинаковым Close — считаем данные не свежими (фид не обновился)."""
    if len(d) < n: return False
    closes = d['Close'].iloc[-n:].tolist()
    return len(set(round(c, 6) for c in closes)) == 1


def box_extremes(d, off, target_date, start_min, end_min):
    """Экстремумы бокса за КОНКРЕТНУЮ ригийскую дату (не обязательно сегодня) — нужно и для
    сегодняшнего бокса, и (ИСПРАВЛЕНО 28.09.2026) для бокса ВЧЕРАШНЕГО торгового дня, который
    требуется для определения bias до выноса (см. ниже)."""
    rows = []
    for ts, row in d.iterrows():
        rt = ts.to_pydatetime() + dt.timedelta(hours=off)
        if rt.date() != target_date: continue
        m = rt.hour * 60 + rt.minute
        if start_min <= m < end_min:
            rows.append(row)
    if not rows: return None
    highs = [r['High'] for r in rows]; lows = [r['Low'] for r in rows]
    return float(max(highs)), float(min(lows))


def prev_trading_date(d):
    """Предыдущий ТОРГОВЫЙ день (пропускает субботу/воскресенье) — те же правила, что уже
    используются в боевом коде (scan.py/nyscan3.py: d.weekday()>=5 пропускается)."""
    p = d - dt.timedelta(days=1)
    while p.weekday() >= 5:
        p -= dt.timedelta(days=1)
    return p


# ИСПРАВЛЕНО 28.09.2026 (по замечанию пользователя после отчёта 10:04: "настрой long/short
# мы определяем ДО выноса верно?"): раньше check_instrument() до самого выноса всегда отдавал
# плоский статус "внутри бокса" / direction "—" — вообще без bias. Это неверно: по базовому
# правилу Пульта (см. трейдинг/система-и-анализ.md, п.2 "Определение bias по Азии/Лондону")
# bias решается ДО открытия Франкфурта/Нью-Йорка простым сравнением сегодняшнего бокса
# (Азия для Типа A / Лондон для Типа C) с ТЕМ ЖЕ боксом вчерашнего торгового дня — это
# чисто механическая проверка, её можно и нужно делать в облаке без графика:
#   - long bias:  сегодняшний хай > вчерашнего, а лоу >= вчерашнего лоу
#   - short bias: сегодняшний лоу < вчерашнего, а хай <= вчерашнего хая
#   - скип (обхват): сегодняшний бокс шире вчерашнего и сверху, и снизу
#   - скип (внутренний день): сегодняшний бокс целиком внутри вчерашнего
# Остальные факторы чек-листа (встречный H1/H4 FVG, многодневный тренд, реальная ликвидность
# по графику) в этом упрощённом облачном скрипте всё ещё НЕ проверяются (нужен график) — это
# по-прежнему решается дискреционно в самом отчёте при просмотре 1D/4H/1H перед 10:00/16:30,
# как и раньше по регламенту (см. система-и-анализ.md, "Порядок работы каждый день").
def _bias(boxH, boxL, pH, pL):
    if pH is None or pL is None:
        return None
    if boxH > pH and boxL < pL:
        return 'skip_envelope'
    if boxH <= pH and boxL >= pL:
        return 'skip_inside'
    if boxH > pH and boxL >= pL:
        return 'long'
    if boxL < pL and boxH <= pH:
        return 'short'
    return None


def check_instrument(sym, ticker, window, prev=None):
    """ИСПРАВЛЕНО 28.09.2026 (3-я правка): вместо упрощённой проверки бокс/bias — ПОЛНЫЙ
    механический разбор по правилам Пульта (pult_rules.analyze): bias, аномальные свечи бокса,
    инвертированный свой H1 FVG, встречный H1 FVG в боксе/на пути, встречный H4 FVG с реакцией,
    противоположная сторона снята первой, вынос закрытием, встречный H1 FVG от выноса,
    выкуп/сильные свечи/m5 FVG, вход v73, блок цели 1:2, ведение сделки TP/SL.
    Повод: пользователь нашёл на EURUSD и US500 встречный H1 FVG, а отчёт показывал НАБЛЮДАЕМ."""
    import pult_rules
    d = fetch(ticker)
    if d is None: return {'sym': sym, 'error': 'no_data'}
    riga_dt, off = riga_now()
    if is_stale(d):
        return {'sym': sym, 'window': window, 'line_status': 'skip', 'direction': '—',
                'note': 'СКИП (нет свежих данных у источника)', 'status_key': 'stale', 'stale': True,
                'price': round(float(d['Close'].iloc[-1]), 5)}
    is_mt5 = bool(len(d)) and SRC.get(sym) == 'MT5' and str(ticker) != 'Yahoo'
    ps = (prev or {}).get('signal') or {}
    if ps and ps.get('src', 'Yahoo') != ('MT5' if is_mt5 else 'Yahoo'):
        d2 = fetch(ticker, ps.get('src', 'Yahoo'))   # ведём сделку по тому же источнику, что и вход
        if d2 is not None: d = d2
    h1 = None
    try:   # часовые бары (~40 суток) — структура Swing/Sub, ликвидность H1/D1, H1 FVG (типы A и C)
        h1 = fetch_ohlc(ticker, '60d', '60m')
    except Exception as e:
        print('H1 недоступен:', sym, str(e)[:100])
    r = pult_rules.analyze(sym, d, window, dt.datetime.utcnow(), off, prev, h1)
    if r.get('signal') is not None and 'src' not in r['signal']:
        r['signal']['src'] = ps.get('src', 'MT5' if is_mt5 else 'Yahoo') if ps else ('MT5' if is_mt5 else 'Yahoo')
    if r.get('error'):
        return {'sym': sym, 'error': r['error']}
    return r


def load_state():
    if os.path.exists(STATE_PATH):
        try: return json.load(open(STATE_PATH))
        except Exception: return {}
    return {}


def save_state(st):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    json.dump(st, open(STATE_PATH, 'w'), ensure_ascii=False, indent=2)


ARTIFACT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'pult_artifact.json')


# ДОБАВЛЕНО 28.09.2026 (вечер): окно закрылось, входов не было = СКИП — то же правило, что
# пользователь попросил для Telegram (см. pult_tick._tg), теперь и для карточек артефакта
# (раньше карточки «Отчёта дня» после закрытия окна продолжали показывать НАБЛЮДАЕМ/ВЫНОС).
WINCLOSE = {'A': 840, 'C': 1110}


def _fold_closed(r, window, riga_dt):
    if riga_dt.hour * 60 + riga_dt.minute < WINCLOSE.get(window, 99999):
        return r
    if r.get('line_status') in ('watch', 'prep') and not r.get('signal'):
        r = dict(r)
        r['line_status'] = 'skip'
        r['direction'] = '—'
        r['note'] = 'СКИП (окно закрылось, входов не было)'
    return r


def build_artifact_payload(state, riga_dt, window, changed_syms, check_text):
    """Данные для артефакта Пульта (коллекции db 'pult' и 'pult_meta'): одна запись на
    инструмент окна + мета-запись с последней проверкой и журналом проверок (строка
    "проверено в HH:MM — без изменений / изменилось: ...")."""
    date = riga_dt.strftime('%Y-%m-%d')
    docs = []
    for sym in WINDOW_SYMBOLS[window]:
        r = state.get(f'{sym}_{window}', {})
        if not r or r.get('error'): continue
        r = _fold_closed(r, window, riga_dt)
        docs.append({'collection': 'pult', 'doc_id': f'{sym}_{window}', 'data': {
            'date': date, 'sym': sym, 'window': window, 'status': r.get('line_status'),
            'direction': r.get('direction'), 'note': r.get('note'), 'reasons': r.get('reasons', []),
            'price': r.get('price'), 'boxH': r.get('boxH'), 'boxL': r.get('boxL'),
            'prevH': r.get('prevH'), 'prevL': r.get('prevL'), 'signal': r.get('signal'),
            'trendH1': r.get('trend_h1'), 'trendD1': r.get('trend_d1'),
            'checked': r.get('checked_at')}})
    # GER40 нет в WINDOW_SYMBOLS (нет надёжного облачного источника цены) — но карточка
    # в Пульте всё равно нужна (испр. 28.09.2026: пользователь не видел карточку GER40),
    # статическая, с пометкой "смотреть вручную".
    if window == 'A':
        g = state.get('GER40_A', {})
        if g.get('date') == date and g.get('line_status'):
            docs.append({'collection': 'pult', 'doc_id': 'GER40_A', 'data': {
                'date': date, 'sym': 'GER40', 'window': 'A', 'status': g.get('line_status'),
                'direction': g.get('direction'), 'note': g.get('note'), 'reasons': g.get('reasons', []),
                'price': g.get('price'), 'boxH': g.get('boxH'), 'boxL': g.get('boxL'),
                'prevH': g.get('prevH'), 'prevL': g.get('prevL'), 'signal': g.get('signal'),
                'checked': g.get('checked_at') or riga_dt.strftime('%H:%M')}})
    log = state.get('_log', [])
    docs.append({'collection': 'pult_meta', 'doc_id': 'last', 'data': {
        'date': date, 'window': window, 'time': riga_dt.strftime('%H:%M'), 'text': check_text,
        'changed': changed_syms, 'log': log[-40:]}})
    json.dump(docs, open(ARTIFACT_JSON, 'w'), ensure_ascii=False, indent=1)
    PULT_DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state', 'pult_docs')
    os.makedirs(PULT_DOCS_DIR, exist_ok=True)
    for x in docs:
        json.dump(x['data'], open(os.path.join(PULT_DOCS_DIR, f"{x['collection']}__{x['doc_id']}.json"), 'w'), ensure_ascii=False)
    return docs


def main(send=True):
    from notify import build_signal
    riga_dt, off = riga_now()
    window = window_now(riga_dt)
    if window is None:
        print('NOCHANGE: окно закрыто, сейчас', riga_dt.strftime('%H:%M'), 'по Риге')
        return
    state = load_state()
    today = riga_dt.strftime('%Y-%m-%d')
    new_state = dict(state)
    changed_lines, unchanged_lines, changed_syms, signals = [], [], [], []
    for sym in WINDOW_SYMBOLS[window]:
        key = f'{sym}_{window}'
        prev = state.get(key, {})
        if prev.get('date') != today:
            prev = {}
        try:
            r = check_instrument(sym, ticker_for(sym, window), window, prev)
        except Exception as e:
            r = {'sym': sym, 'error': str(e)}
        if r.get('error'):
            print('ERROR', sym, r['error'])
            continue
        r['date'] = today
        new_state[key] = r
        line = fmt_line(r['line_status'], sym, r['direction'], r['note'])
        if (r.get('line_status'), r.get('direction'), r.get('note')) != (prev.get('line_status'), prev.get('direction'), prev.get('note')):
            changed_lines.append(line); changed_syms.append(sym)
        else:
            unchanged_lines.append(line)
        if r.pop('new_signal', False):
            signals.append(r)
    t = riga_dt.strftime('%H:%M')
    check_text = ('изменилось: ' + ', '.join(f"{s}" for s in changed_syms)) if changed_syms else 'без изменений'
    log = new_state.get('_log', [])
    if log and log[-1].get('date') != today: log = []
    log.append({'date': today, 'time': t, 'window': window, 'text': check_text,
                'lines': changed_lines})
    new_state['_log'] = log[-60:]
    save_state(new_state)
    build_artifact_payload(new_state, riga_dt, window, changed_syms, check_text)
    for r in signals:
        sg = r['signal']
        txt = build_signal(riga_dt.strftime('%d.%m.%Y'), window, sg['time'], r['sym'], r['direction'],
                           sg['entry'], sg['stop'], sg['tp'], 1.0, note='по правилам Пульта, проверь график')
        if send: send_telegram(txt)
        print('SIGNAL'); print(txt)
    if changed_lines:
        text = build_update(riga_dt.strftime('%d.%m.%Y'), window, t, changed_lines, unchanged_lines)
        ok = send_telegram(text) if send else False
        print('CHANGED'); print(text); print('telegram_sent:', ok)
    else:
        print('NOCHANGE: без изменений', t)
    print('ARTIFACT_JSON:', ARTIFACT_JSON)


if __name__ == '__main__':
    main(send='--no-send' not in sys.argv)
