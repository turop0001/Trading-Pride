#!/usr/bin/env python3
"""Автопостинг для @trading_pride (01.11.2026).
Раз в день: читает публичные страницы ~20 трейдинг-каналов ТОЛЬКО ради тем и ажиотажа,
пишет 2 ОРИГИНАЛЬНЫХ поста (новости / умное / смешное / мотивация), присылает владельцу в личку
с кнопками «Опубликовать / Отклонить». Публикует в канал веб-хук /api/tgbot после нажатия кнопки.
Чужие тексты не копируются и не переписываются: источники нужны только как список тем и фактов.
Секреты (GitHub): ANTHROPIC_API_KEY, CP_BOT_TOKEN (или TG_BOT_TOKEN), CP_OWNER_ID (или TG_CHAT_ID).
CP_DRY=1 — ничего не отправлять, только показать черновики."""
import os, re, json, html, datetime as dt, urllib.request, urllib.error, base64

HERE = os.path.dirname(os.path.abspath(__file__))
CH = json.load(open(os.path.join(HERE, 'sources.json'), encoding='utf-8'))['channels']
TOKEN = os.environ.get('CP_BOT_TOKEN') or os.environ.get('TG_BOT_TOKEN', '')
OWNER = os.environ.get('CP_OWNER_ID') or os.environ.get('TG_CHAT_ID', '')
API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
MODEL = os.environ.get('CP_MODEL', 'claude-sonnet-4-5')
DRY = os.environ.get('CP_DRY', '') == '1'
REPO = os.environ.get('GITHUB_REPOSITORY', 'turop0001/Trading-Pride')
GH = os.environ.get('GITHUB_TOKEN', '')
DRAFTS = 'channel/drafts.json'
BRANCH = 'state'
CATS = {'news': 'ХАЙПОВАЯ НОВОСТЬ про рынки/трейдинг', 'smart': 'УМНАЯ МЫСЛЬ про трейдинг (механика рынка, риск, дисциплина)',
        'humor': 'СМЕШНОЕ про трейдинг (своя шутка/ситуация, не копия мема)', 'motiv': 'МОТИВАЦИЯ для развития и польза (конкретный совет/привычка)'}


def http(url, data=None, headers=None, method=None, timeout=40):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def views_num(s):
    s = (s or '').replace(',', '.').strip()
    try:
        if s.endswith('K'): return int(float(s[:-1]) * 1000)
        if s.endswith('M'): return int(float(s[:-1]) * 1000000)
        return int(float(s))
    except Exception:
        return 0


def fetch(u):
    """Свежие посты публичной страницы канала: [(views, text)] за последние ~30 ч."""
    out = []
    try:
        page = http('https://t.me/s/' + u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
    except Exception as e:
        print('  ! ' + u + ': ' + str(e)[:80]); return out
    now = dt.datetime.now(dt.timezone.utc)
    for blk in page.split('tgme_widget_message_wrap')[1:]:
        m = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S)
        if not m: continue
        t = re.sub(r'<br\s*/?>', ' ', m.group(1)); t = re.sub(r'<[^>]+>', '', t); t = html.unescape(t)
        t = re.sub(r'https?://\S+|t\.me/\S+|@\w+', '', t); t = re.sub(r'\s+', ' ', t).strip()
        d = re.search(r'datetime="([^"]+)"', blk)
        try:
            when = dt.datetime.fromisoformat(d.group(1))
            if (now - when).total_seconds() > 30 * 3600: continue
        except Exception:
            continue
        v = re.search(r'tgme_widget_message_views">([^<]+)<', blk)
        if len(t) > 40: out.append((views_num(v.group(1) if v else ''), t[:300]))
    return out


def collect():
    rows = []
    for c in CH:
        got = sorted(fetch(c['u']), reverse=True)[:4]
        print('  %-24s %d' % (c['u'], len(got)))
        for v, t in got: rows.append((v, c['cat'], t))
    rows.sort(reverse=True)
    return rows[:45]


def plan(today):
    """Какие 2 поста писать: будни = новость + (умное/смешное/мотивация по кругу); выходные = две не-новости."""
    rot = ['smart', 'humor', 'motiv']
    n = today.toordinal()
    if today.weekday() < 5: return ['news', rot[n % 3]]
    return [rot[n % 3], rot[(n + 1) % 3]]


def ask_llm(cats, rows, today):
    src = '\n'.join('[%s] %s' % (cat, t) for v, cat, t in rows) or '(источники сегодня пусты)'
    want = '\n'.join('%d) %s' % (i + 1, CATS[c]) for i, c in enumerate(cats))
    prompt = f"""Ты редактор телеграм-канала @trading_pride (трейдинг: форекс, индексы, акции; без крипты). Дата: {today}.
Ниже — темы и обрывки из популярных трейдинг-каналов за сутки. Это ТОЛЬКО сырьё для понимания, что обсуждают сегодня.
Напиши {len(cats)} ОРИГИНАЛЬНЫХ поста на русском:
{want}

ЖЁСТКИЕ ПРАВИЛА:
- Пиши с нуля своими словами и своей структурой. Не повторяй формулировки, заголовки, шутки и порядок мысли источников.
- Новость: только мировые события, способные двигать ФОРЕКС и ИНДЕКСЫ (ФРС и другие ЦБ, макростатистика США/ЕС/Британии/Японии/Китая, нефть и золото, геополитика с реальным рыночным эффектом, отчёты мегакомпаний). Крипту и локальные российские темы не используй. Источники могут быть на английском: излагай факты своими словами по-русски. Берись за тему, которая встречается в нескольких источниках или набрала много просмотров.
- Новость: выбирай только то, что влияет на рынки (центробанки, макростатистика, отчёты, нефть/золото/валюты/индексы, крупные сделки); политику и происшествия без рыночного эффекта пропускай.
- Новость: только факты, которые есть в сырье (лучше в нескольких источниках); никаких выдуманных цифр, дат, имён. Нет уверенности — выбери другую тему или сформулируй осторожно («пишут о…»). Добавь 1 нейтральную строку «что это значит для трейдера», без прогнозов цены.
- Никаких призывов купить/продать, гарантий, «сигналов», обещаний дохода.
- Без ссылок, без @упоминаний, без названий чужих каналов.
- 350–900 символов, живой тон, абзацы по 1–3 предложения, максимум 2 эмодзи, без markdown-разметки (обычный текст).
- Смешное — своя ситуация из жизни трейдера (стоп, спред, «ещё одна свеча»), добрый юмор, без оскорблений.
Верни ТОЛЬКО JSON: {{"posts":[{{"cat":"news|smart|humor|motiv","text":"..."}}]}} — ровно {len(cats)} поста в том же порядке.

СЫРЬЁ:
{src}"""
    body = json.dumps({'model': MODEL, 'max_tokens': 2500, 'messages': [{'role': 'user', 'content': prompt}]}).encode()
    resp = json.loads(http('https://api.anthropic.com/v1/messages', body, {'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}, 'POST', 120))
    txt = ''.join(b.get('text', '') for b in resp.get('content', []))
    j = json.loads(txt[txt.find('{'):txt.rfind('}') + 1])
    return j.get('posts', [])


BAD = re.compile(r'https?://|t\.me|@\w|гарантир|100\s*%\s*прибыл|купи(те)?\b|продавай', re.I)


def valid(p):
    t = p.get('text', '')
    return p.get('cat') in CATS and 200 <= len(t) <= 1100 and not BAD.search(t)


def gh(method, path, data=None):
    h = {'Authorization': 'Bearer ' + GH, 'Accept': 'application/vnd.github+json'}
    if data is not None: h['Content-Type'] = 'application/json'
    return json.loads(http('https://api.github.com/repos/%s/%s' % (REPO, path), json.dumps(data).encode() if data is not None else None, h, method))


def load_drafts():
    try:
        r = gh('GET', 'contents/%s?ref=%s' % (DRAFTS, BRANCH))
        return json.loads(base64.b64decode(r['content']).decode()), r['sha']
    except urllib.error.HTTPError:
        return {}, None


def save_drafts(d, sha):
    keep = dict(sorted(d.items())[-60:])
    body = {'message': 'channel: черновики', 'branch': BRANCH, 'content': base64.b64encode(json.dumps(keep, ensure_ascii=False, indent=1).encode()).decode()}
    if sha: body['sha'] = sha
    gh('PUT', 'contents/' + DRAFTS, body)


def tg(method, payload):
    return json.loads(http('https://api.telegram.org/bot%s/%s' % (TOKEN, method), json.dumps(payload).encode(), {'Content-Type': 'application/json'}, 'POST'))


def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    print('Читаю каналы (только темы):'); rows = collect()
    cats = plan(today); print('План:', cats, '· сырья:', len(rows))
    posts = []
    if API_KEY:
        try:
            for _ in range(2):
                posts = [p for p in ask_llm(cats, rows, today) if valid(p)]
                if len(posts) == len(cats): break
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:300]
            print('Ошибка API Anthropic:', e.code, body)
            hint = 'Пополните баланс на console.anthropic.com → Billing.' if 'credit' in body.lower() or e.code in (400, 402) else 'Проверьте ключ ANTHROPIC_API_KEY.'
            if TOKEN and OWNER and not DRY:
                try: tg('sendMessage', {'chat_id': OWNER, 'text': 'Автопостинг: не удалось написать черновики (код %s). %s' % (e.code, hint)})
                except Exception: pass
            return
    else:
        print('НЕТ ANTHROPIC_API_KEY — черновики не сгенерированы')
    if not posts: print('Нет годных черновиков — выходим'); return
    for p in posts: print('\n--- %s ---\n%s' % (p['cat'], p['text']))
    if DRY: print('\nCP_DRY=1: ничего не отправлено'); return
    if not (TOKEN and OWNER): print('НЕТ CP_BOT_TOKEN/CP_OWNER_ID'); return
    drafts, sha = load_drafts()
    for i, p in enumerate(posts):
        did = '%s-%d' % (today.strftime('%Y%m%d'), i + 1)
        drafts[did] = {'cat': p['cat'], 'text': p['text'], 'status': 'pending', 'ts': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}
        tg('sendMessage', {'chat_id': OWNER, 'text': 'Черновик %s · %s\n\n%s' % (did, p['cat'], p['text']),
                           'reply_markup': {'inline_keyboard': [[{'text': '✅ Опубликовать', 'callback_data': 'ap:' + did}, {'text': '❌ Отклонить', 'callback_data': 'rj:' + did}]]}})
    save_drafts(drafts, sha)
    print('Отправлено на одобрение:', len(posts))


if __name__ == '__main__':
    main()
