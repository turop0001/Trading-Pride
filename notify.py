#!/usr/bin/env python3
"""Общий облачный модуль отправки + форматирование сообщений Пульта.
Используется live_check.py и report-задачами (через
python3 -c "from sys import path; path.insert(0,'/home/claude/ts/full'); from notify import ...").
Ничего не требует локального компьютера пользователя.

Формат сообщений — по образцу, который пользователь прислал 26.09.2026 (структура + эмодзи).
"""
import json, os, urllib.request, urllib.parse

# ПЕРЕНОС НА GITHUB ACTIONS (29.09.2026): токен и chat_id теперь берутся из переменных
# окружения (GitHub Secrets: TG_BOT_TOKEN, TG_CHAT_ID, необязательно TG_THREAD_ID) —
# так секреты не лежат в репозитории открытым текстом. CFG_PATH оставлен как запасной
# путь (для локального запуска вне GitHub Actions, если такой файл всё же есть рядом).
CFG_PATH = os.environ.get('TG_CONFIG_PATH', 'tg_config.json')

# --- emoji-конвенция (выбор пользователя: "Текст + смайлы-маркеры статуса") ---
E_ENTRY = '\U0001F7E2'    # 🟢 вход / подтверждено / вынос в сторону сделки
E_SKIP  = '⚪'        # ⚪ скип (в стиле присланного образца)
E_STOP  = '\U0001F534'    # 🔴 стоп/отмена (используется отдельно, не для рутинного скипа)
E_WATCH = '\U0001F7E1'    # 🟡 наблюдаем / внутри бокса, вынос ещё не подтверждён
E_NEWS  = '⚠️'  # ⚠️ новости / риск
E_BELL  = '\U0001F6CE️'  # 🛎️ заголовок отчёта/сигнала
E_CHART = '\U0001F4CA'    # 📊 отчёт/обновление
E_CLOCK = '\U0001F570️'  # 🕰️ окно закрыто (мантийные часы, с VS16)
E_DOT   = '\U0001F538'    # 🔸 пункт
E_EYES  = '\U0001F440'    # 👀 наблюдаем (секция)
E_TARGET = '\U0001F3AF'   # 🎯 цель/тейк
E_MONEY = '\U0001F4B0'    # 💰 итог по деньгам
E_NEXT  = '⏰'        # ⏰ следующее окно
E_OPEN  = '\U0001F7E2'    # 🟢 окно открыто
E_CLOSED = '\U0001F6D1'   # 🛑 окно закрыто
E_PREP  = '⚠️'   # ⚠️ ГОТОВИМСЯ — вынос/выкуп уже идёт, это НЕ то же самое, что жёлтое "наблюдаем"
                     # (испр. 28.09.2026 по просьбе пользователя: разные значки для разных стадий)

DIR_LONG = '▲ LONG'    # ▲ LONG (подтверждённое направление — уже был вынос своей стороны)
DIR_SHORT = '\U0001F53B SHORT'  # 🔻 SHORT
# ИСПРАВЛЕНО 28.09.2026 (повторно): LONG-маркер сменён с 🔺 на чёрный треугольник ▲ по
# прямой просьбе пользователя, во всех отчётах/обновлениях/сигналах — SHORT остаётся 🔻.
# ИСПРАВЛЕНО 29.09.2026: слово "bias" убрано из всех текстов Telegram, DIR_BIAS_* удалены.


def fmt_line(status, symbol, direction, note):
    """status: 'skip' | 'entry' | 'watch' | 'prep'. Одна строка по инструменту.
    ИСПРАВЛЕНО 28.09.2026: note — короткое слово статуса ("НАБЛЮДАЕМ"/"СКИП"/"ГОТОВИМСЯ",
    с необязательной краткой пометкой в скобках у ГОТОВИМСЯ), а не полное предложение —
    подробности (bias/причина) переехали в direction, тоже в короткой форме."""
    emo = {'skip': E_SKIP, 'entry': E_ENTRY, 'watch': E_WATCH, 'prep': E_PREP}.get(status, E_WATCH)
    if 'ЗАКРЫТА - SL' in str(note):
        emo = E_STOP  # 🔴 стоп; ⚪ только для СКИП
    return f"{emo} {symbol} ({direction}) — {note}"


# ИСПРАВЛЕНО 28.09.2026 (по образцу пользователя, отчёт 10:04 переделан): отчёт ОТКРЫТИЯ
# окна (10:00 Тип A / 16:30 Тип C) — это отдельный, короткий формат: только per-инструмент
# статус (bias уже определён ДО выноса — long/short/скип по сравнению с вчерашним боксом)
# и ссылка на следующее окно. БЕЗ "итог дня" и БЕЗ блока новостей — их здесь никогда не было
# по методологии (см. трейдинг/система-и-анализ.md), они по ошибке добавлялись в старый
# промпт report-задачи. "Итог дня" появляется только в build_daily_summary (после закрытия
# ОБОИХ окон, вечером). Новости даём отдельной строкой только если сам пользователь просит.
def build_window_open(date, window_label, window_range, lines, next_label=None, next_time=None):
    head = f"{E_BELL} Отчёт· {date} · Окно {window_label} ({window_range} Рига) открыто {E_OPEN}\n\n"
    body = "\n".join(lines)
    tail = ""
    if next_label and next_time:
        tail = f"\n\n{E_NEXT} Следующее окно — тип {next_label} (NY), старт {next_time} Рига."
    return head + body + tail


def build_window_closed(date, window_label, window_range, lines, next_label=None, next_time=None,
                         trades=0, pct=0.0, end_time=None):
    """Отчёт закрытия окна без сделок (или с ними — lines уже готовые строки по инструментам)."""
    head = f"{E_BELL} Отчёт · {date} · Окно {window_label} ({window_range} Рига) закрыто {E_CLOSED}\n\n"
    sign = '+' if pct > 0 else ('-' if pct < 0 else '')
    head += f"{E_CHART} Итог окна {window_label}: {trades} сделок, {sign}{abs(pct):.1f}% депозита\n\n"
    if end_time:
        head += f"{E_CLOCK} Окно {window_label} закрыто в {end_time} Рига.\n"
    if trades == 0:
        head += f"{E_DOT} Сделок по типу {window_label} сегодня не было\n"
        head += f"{E_DOT} все {len(lines)} инструментов закрылись скипом:\n\n"
    body = "\n".join(lines)
    tail = ""
    if next_label and next_time:
        tail = f"\n\n{E_NEXT} Следующее окно — (тип {next_label}), старт ({next_time} Рига)."
    return head + body + tail


def build_update(date, window_label, time_str, changed_lines, unchanged_lines=None):
    """changed_lines — строки инструментов, у которых статус ИЗМЕНИЛСЯ с прошлой проверки
    (это и есть сама суть "Обновления"). unchanged_lines — остальные, группой "Без изменений:"
    (испр. 28.09.2026: раньше заголовок группы был "Наблюдаем", хотя туда попадали и скип-строки —
    неточно; по образцу пользователя правильный заголовок именно "Без изменений:")."""
    head = f"{E_CHART} Обновление · окно {window_label} · {date} ({time_str} Рига)\n\n"
    body = "\n".join(changed_lines)
    tail = ""
    if unchanged_lines:
        tail = f"\n\nБез изменений:\n" + "\n".join(unchanged_lines)
    return head + body + tail


def build_signal(date, window_label, time_str, symbol, direction, entry, stop, target_2r, risk_pct, note='есть order flow', rr=2):
    return (f"{E_BELL} СИГНАЛ · тип {window_label} · {date} ({time_str} Рига)\n\n"
            f"{E_ENTRY} {symbol} ({direction}):\n\n"
            f"Вход {entry} · {time_str}\n"
            f"Стоп: {stop}\n"
            f"{E_TARGET} Цель {float(rr):g}R: {target_2r}\n"
            f"{E_NEWS} Риск: {risk_pct}%")


def build_tp_hit(symbol, direction, target_price, time_str, pct):
    return (f"{E_ENTRY} {symbol} ({direction}) — TP {E_TARGET} +2R по {target_price} ({time_str} Рига)\n"
            f"{E_MONEY} Итог: {pct:+.1f}% депозита")


def build_daily_summary(date, sections, total_pct):
    """sections: список (window_label, [entry/skip-строки], [наблюдаем-строки на watch])."""
    out = [f"{E_CHART} Отчёт дня · {date}\n"]
    for label, lines, watch in sections:
        out.append(f"Тип {label}:")
        out.extend(lines)
        if watch:
            out.append(f"\n{E_EYES} Наблюдаем (без выноса):")
            out.append(", ".join(watch))
        out.append("")
    sign = '+' if total_pct > 0 else ('-' if total_pct < 0 else '')
    out.append(f"{E_TARGET} Итог дня: {sign}{abs(total_pct):.1f}% депозита")
    return "\n".join(out)

# --- Недельный отчёт (утверждён пользователем 06.10.2026): пятница 22:00 Рига, риск 1% на сделку, отдельно Тип A и C ---
import re as _re

def _weekly_parse(item):
    """Закрытая сделка из state/history.json → (out, r) или None. out: TP / SL / BE; r — результат в R (1R = 1% депозита)."""
    res = str(item.get('result') or '')
    if 'ВХОД' not in res and 'ЗАКРЫТА' not in res: return None
    m = _re.search(r'([+\u2212\-]\d+(?:[.,]\d+)?)\s*R', res)
    val = float(m.group(1).replace('\u2212', '-').replace(',', '.')) if m else None
    if 'TP' in res: return 'TP', (val if val is not None else 2.0)
    if 'SL' in res: return 'SL', -1.0
    if 'БУ' in res: return 'BE', 0.0
    if '22:00' in res and val is not None:
        return ('TP' if val > 0 else 'SL' if val < 0 else 'BE'), val
    return None


def _fmt_r(x):
    return ('+' if x > 0 else '\u2212' if x < 0 else '') + f"{abs(x):.1f}"


def build_weekly(mon, fri, items):
    """mon/fri — datetime.date (понедельник и пятница недели); items — записи state/history.json."""
    rows = {'A': [], 'C': []}
    for it in sorted(items, key=lambda x: (x.get('date') or '', x.get('symbol') or '')):
        d = it.get('date') or ''
        if not (str(mon) <= d <= str(fri)): continue
        t = it.get('type')
        if t not in rows: continue
        p = _weekly_parse(it)
        if not p: continue
        rows[t].append((d, it.get('symbol'), it.get('side'), p[0], p[1]))
    out = [f"{E_CHART} Недельный отчёт · {mon.strftime('%d.%m')} \u2013 {fri.strftime('%d.%m.%Y')}",
           "(пятница, 22:00 Рига · риск 1% на сделку)", ""]
    tot_n = tot_tp = tot_sl = tot_be = 0
    tot_r = 0.0
    for t in ('A', 'C'):
        r = rows[t]
        out.append(f"Тип {t}:")
        if not r:
            out.append("Сделок не было")
            out.append(f"{E_TARGET} Тип {t}: 0.0R · 0.0% депозита")
            out.append("")
            continue
        for d, sym, side, o, x in r:
            emo = E_ENTRY if o == 'TP' else E_STOP if o == 'SL' else E_WATCH
            dirr = DIR_LONG if side == 'long' else DIR_SHORT
            word = 'TP' if o == 'TP' else 'SL' if o == 'SL' else '\u0411\u0423'
            out.append(f"{emo} {d[8:10]}.{d[5:7]} {sym} ({dirr}) \u2014 {word} {_fmt_r(x)}%")
        n = len(r); tp = sum(1 for x in r if x[3] == 'TP'); sl = sum(1 for x in r if x[3] == 'SL'); be = n - tp - sl
        rr = sum(x[4] for x in r)
        out.append("")
        out.append(f"\u0421\u0434\u0435\u043b\u043e\u043a {n} \u00b7 {E_ENTRY} TP {tp} \u00b7 {E_STOP} SL {sl}" + (f" \u00b7 {E_WATCH} \u0411\u0423 {be}" if be else "") + f" \u00b7 WR {round(tp / n * 100)}%")
        out.append(f"{E_TARGET} \u0422\u0438\u043f {t}: {_fmt_r(rr)}R \u00b7 {_fmt_r(rr)}% \u0434\u0435\u043f\u043e\u0437\u0438\u0442\u0430")
        out.append("")
        tot_n += n; tot_tp += tp; tot_sl += sl; tot_be += be; tot_r += rr
    wr = round(tot_tp / tot_n * 100) if tot_n else 0
    out.append(f"{E_CHART} \u0418\u0442\u043e\u0433\u043e \u0437\u0430 \u043d\u0435\u0434\u0435\u043b\u044e: {tot_n} \u0441\u0434\u0435\u043b\u043e\u043a \u00b7 {E_ENTRY} TP {tot_tp} \u00b7 {E_STOP} SL {tot_sl}" + (f" \u00b7 {E_WATCH} \u0411\u0423 {tot_be}" if tot_be else "") + f" \u00b7 WR {wr}%")
    out.append(f"{E_TARGET} \u0418\u0442\u043e\u0433 \u043d\u0435\u0434\u0435\u043b\u0438: {_fmt_r(tot_r)}R \u00b7 {_fmt_r(tot_r)}% \u0434\u0435\u043f\u043e\u0437\u0438\u0442\u0430")
    return "\n".join(out)



def send_telegram(text: str) -> bool:
    tok = os.environ.get('TG_BOT_TOKEN', '')
    chat = os.environ.get('TG_CHAT_ID', '')
    thread_id = os.environ.get('TG_THREAD_ID') or None
    if not tok or not chat:
        # запасной путь — локальный tg_config.json (не в GitHub Actions)
        if os.path.exists(CFG_PATH):
            cfg = json.load(open(CFG_PATH))
            tok, chat = cfg.get('bot_token', ''), str(cfg.get('chat_id', ''))
            thread_id = cfg.get('message_thread_id')
    if not tok or not chat:
        print('НЕТ TG_BOT_TOKEN/TG_CHAT_ID (ни в env, ни в tg_config.json) — телеграм не отправлен')
        return False
    params = {'chat_id': chat, 'text': text}
    if thread_id:
        params['message_thread_id'] = thread_id
    data = urllib.parse.urlencode(params).encode()
    try:
        r = urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data, timeout=20)
        ok = json.load(r).get('ok', False)
        print('telegram_sent:', ok)
        return ok
    except Exception as e:
        print('ошибка telegram:', str(e).replace(tok, '***'))
        return False


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--selftest':
        print('notify.py OK, tg_config.json существует:', os.path.exists(CFG_PATH))
    else:
        print('Использование: from notify import send_telegram, fmt_line, build_window_open, '
              'build_window_closed, build_update, build_signal, build_tp_hit, build_daily_summary')
