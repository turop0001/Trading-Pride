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
- ФОРМАТ как у лучших телеграм-каналов: КОРОТКО, 250–600 символов. Первая строка — цепляющий заголовок-крючок (до 70 символов, с одним уместным эмодзи в начале). Дальше 2–4 короткие строки/абзаца по 1–2 предложения, в начале ключевых строк уместные эмодзи по смыслу (📉📈🏦🛢🥇⚠️💡🔥😅 и т.п.), всего 3–6 эмодзи на пост, без перебора. Живой разговорный тон, без воды и канцелярита. Разметку (markdown/HTML/звёздочки) не используй.
- Для КАЖДОГО поста добавь "media": {"type":"photo|video|gif|card","query":"2–4 слова НА АНГЛИЙСКОМ для поиска подходящего бесплатного фото/видео/гифки (например: stock market screen, trader stress, gold bars, oil rig, success sunrise)"}. Новости/умное: photo или video; смешное: gif; мотивация: photo или video; если не уверен — card.
- Для КАЖДОГО поста добавь "card": короткая надпись для картинки — "title" (2–6 слов, КАПСОМ не нужно, без эмодзи, цепляет суть) и "sub" (до 6 слов, можно пусто).
- Смешное — своя ситуация из жизни трейдера (стоп, спред, «ещё одна свеча»), добрый юмор, без оскорблений.
Верни ТОЛЬКО JSON: {{"posts":[{{"cat":"news|smart|humor|motiv","text":"...","media":{{"type":"..","query":".."}},"card":{{"title":"...","sub":"..."}}}}]}} — ровно {len(cats)} поста в том же порядке.

СЫРЬЁ:
{src}"""
    body = json.dumps({'model': MODEL, 'max_tokens': 3000, 'messages': [{'role': 'user', 'content': prompt}]}).encode()
    resp = json.loads(http('https://api.anthropic.com/v1/messages', body, {'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}, 'POST', 120))
    txt = ''.join(b.get('text', '') for b in resp.get('content', []))
    j = json.loads(txt[txt.find('{'):txt.rfind('}') + 1])
    return j.get('posts', [])


BAD = re.compile(r'https?://|t\.me|@\w|гарантир|100\s*%\s*прибыл|купи(те)?\b|продавай', re.I)


def valid(p):
    t = p.get('text', '')
    return p.get('cat') in CATS and 200 <= len(t) <= 800 and not BAD.search(t) and sum(1 for ch in t if ord(ch) > 0x2000) >= 2 and 2 <= len((p.get('card') or {}).get('title', '')) <= 60


PALETTE = {'news': ((10, 25, 60), (30, 90, 200), 'НОВОСТИ РЫНКА'), 'smart': ((20, 20, 40), (90, 50, 160), 'ТРЕЙДЕРУ НА ЗАМЕТКУ'),
           'humor': ((70, 30, 10), (230, 120, 30), 'ТРЕЙДЕРСКИЙ ЮМОР'), 'motiv': ((6, 50, 45), (20, 160, 120), 'РОСТ И ДИСЦИПЛИНА')}


def make_card(cat, card, path):
    """Оригинальная картинка 1080x1080: градиент по рубрике + крупный заголовок + свечной узор. Без чужих изображений."""
    from PIL import Image, ImageDraw, ImageFont
    import random
    a, b, tag = PALETTE.get(cat, PALETTE['news']); W = 1080
    img = Image.new('RGB', (W, W)); px = img.load()
    for y in range(W):
        for x in range(W):
            k = (x + y) / (2 * W); px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
    d = ImageDraw.Draw(img, 'RGBA'); rnd = random.Random(card.get('title', ''))
    price = 880; x0 = 60
    for i in range(16):   # декоративные свечи
        o = price; price += rnd.randint(-45, 38); price = max(740, min(980, price)); h = abs(price - o) + 20
        top = min(o, price) - 10; col = (255, 255, 255, 70) if price <= o else (255, 255, 255, 38)
        d.line([(x0 + 24, top - 30), (x0 + 24, top + h + 30)], fill=(255, 255, 255, 60), width=3)
        d.rectangle([x0, top, x0 + 48, top + h], fill=col); x0 += 63
    def font(sz, bold=True):
        for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf' % ('-Bold' if bold else ''), '/usr/share/fonts/dejavu/DejaVuSans%s.ttf' % ('-Bold' if bold else '')):
            if os.path.exists(f): return ImageFont.truetype(f, sz)
        return ImageFont.load_default()
    d.rounded_rectangle([60, 70, 60 + 22 * len(tag) + 50, 140], 35, fill=(255, 255, 255, 40))
    d.text((85, 83), tag, font=font(34), fill=(255, 255, 255, 235))
    title = card.get('title', '').strip(); sz = 120
    while sz > 56:
        f = font(sz); lines = []; cur = ''
        for w in title.split():
            t = (cur + ' ' + w).strip()
            if d.textlength(t, font=f) <= W - 130: cur = t
            else: lines.append(cur); cur = w
        lines.append(cur)
        if len(lines) <= 4 and all(d.textlength(l, font=f) <= W - 130 for l in lines): break
        sz -= 8
    y = 230
    for l in lines:
        d.text((64, y + 4), l, font=f, fill=(0, 0, 0, 90)); d.text((60, y), l, font=f, fill='white'); y += int(sz * 1.18)
    sub = (card.get('sub') or '').strip()
    if sub: d.text((60, y + 20), sub, font=font(46, False), fill=(255, 255, 255, 215))
    d.text((60, 1005), '@trading_pride', font=font(36), fill=(255, 255, 255, 200))
    img.save(path, 'PNG')


PIXABAY = os.environ.get('PIXABAY_KEY', ''); PEXELS = os.environ.get('PEXELS_KEY', ''); GIPHY = os.environ.get('GIPHY_KEY', '')


def find_media(m, cat):
    """Лицензионные площадки: Pexels (фото/видео, свободная лицензия) и Giphy API. Нет ключа/результата -> None (будет карточка)."""
    import urllib.parse
    typ, q = (m or {}).get('type', 'card'), urllib.parse.quote((m or {}).get('query', '') or 'trading')
    try:
        if typ == 'gif' and GIPHY:
            r = json.loads(http('https://api.giphy.com/v1/gifs/search?api_key=%s&q=%s&limit=12&rating=pg-13&lang=en' % (GIPHY, q)))['data']
            for g in r:
                u = g['images'].get('downsized_large', {}).get('url') or g['images']['original']['url']
                if int(g['images'].get('downsized_large', {}).get('size', 0) or 0) < 15000000: return ('animation', u)
        if typ == 'video' and PIXABAY:
            for v in json.loads(http('https://pixabay.com/api/videos/?key=%s&q=%s&per_page=10&safesearch=true' % (PIXABAY, q)))['hits']:
                if v.get('duration', 99) > 25: continue
                m = v['videos'].get('medium') or v['videos'].get('small')
                if m and m.get('size', 0) < 18000000: return ('video', m['url'])
        if typ in ('photo', 'video') and PIXABAY:
            h = json.loads(http('https://pixabay.com/api/?key=%s&q=%s&image_type=photo&orientation=horizontal&safesearch=true&per_page=10' % (PIXABAY, q)))['hits']
            if h: return ('photo', h[0]['largeImageURL'])
        if typ == 'video' and PEXELS:
            r = json.loads(http('https://api.pexels.com/videos/search?query=%s&per_page=8&size=medium&orientation=landscape' % q, headers={'Authorization': PEXELS}))['videos']
            for v in r:
                if v.get('duration', 99) > 25: continue
                fs = [f for f in v['video_files'] if f.get('file_type') == 'video/mp4' and 600 <= (f.get('width') or 0) <= 1300]
                if fs: return ('video', sorted(fs, key=lambda f: f['width'])[-1]['link'])
        if typ in ('photo', 'video') and PEXELS:
            r = json.loads(http('https://api.pexels.com/v1/search?query=%s&per_page=8&orientation=landscape' % q, headers={'Authorization': PEXELS}))['photos']
            if r: return ('photo', r[0]['src']['large'])
    except Exception as e:
        print('! медиа не найдено:', str(e)[:100])
    return None


def send_url_media(chat, kind, url, caption, kb):
    f = {'photo': 'photo', 'video': 'video', 'animation': 'animation'}[kind]
    p = {'chat_id': chat, f: url, 'caption': caption[:1024], 'parse_mode': 'HTML', 'reply_markup': kb}
    if kind == 'video': p['supports_streaming'] = True
    r = tg('send' + kind.capitalize(), p)['result']
    return r['photo'][-1]['file_id'] if kind == 'photo' else r[kind]['file_id']


def html_text(t):
    t = html.escape(t, quote=False); l = t.split('\n', 1)
    return '<b>' + l[0] + '</b>' + ('\n' + l[1] if len(l) > 1 else '')


def send_photo(chat, path, caption, kb):
    import uuid
    bd = uuid.uuid4().hex; parts = []
    def fld(n, v): parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (bd, n, v)).encode())
    fld('chat_id', chat); fld('caption', caption[:1024]); fld('parse_mode', 'HTML'); fld('reply_markup', json.dumps(kb))
    parts.append(('--%s\r\nContent-Disposition: form-data; name="photo"; filename="c.png"\r\nContent-Type: image/png\r\n\r\n' % bd).encode() + open(path, 'rb').read() + b'\r\n')
    parts.append(('--%s--\r\n' % bd).encode())
    return json.loads(http('https://api.telegram.org/bot%s/sendPhoto' % TOKEN, b''.join(parts), {'Content-Type': 'multipart/form-data; boundary=' + bd}, 'POST', 60))


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
        kb = {'inline_keyboard': [[{'text': '✅ Опубликовать', 'callback_data': 'ap:' + did}, {'text': '❌ Отклонить', 'callback_data': 'rj:' + did}]]}
        try:
            got = find_media(p.get('media'), p['cat'])
            if got:
                try:
                    drafts[did]['photo'] = send_url_media(OWNER, got[0], got[1], html_text(p['text']), kb); drafts[did]['kind'] = got[0]
                except Exception as e:
                    print('! стоковое медиа не отправилось, делаю карточку:', str(e)[:100]); got = None
            if not got:
                png = '/tmp/card_%s.png' % did; make_card(p['cat'], p['card'], png)
                r = send_photo(OWNER, png, html_text(p['text']), kb)
                drafts[did]['photo'] = r['result']['photo'][-1]['file_id']; drafts[did]['kind'] = 'photo'
        except Exception as e:
            print('! картинка не вышла, шлю текстом:', str(e)[:120])
            tg('sendMessage', {'chat_id': OWNER, 'text': 'Черновик %s · %s\n\n%s' % (did, p['cat'], p['text']), 'reply_markup': kb})
    save_drafts(drafts, sha)
    print('Отправлено на одобрение:', len(posts))


if __name__ == '__main__':
    main()
