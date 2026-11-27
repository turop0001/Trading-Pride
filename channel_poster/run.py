#!/usr/bin/env python3
"""Автопостинг для @trading_pride (01.11.2026).
Раз в день: читает публичные страницы ~20 трейдинг-каналов ТОЛЬКО ради тем и ажиотажа,
пишет 2 ОРИГИНАЛЬНЫХ поста (новости / умное / смешное / мотивация), присылает владельцу в личку
с кнопками «Опубликовать / Отклонить». Публикует в канал веб-хук /api/tgbot после нажатия кнопки.
Чужие тексты не копируются и не переписываются: источники нужны только как список тем и фактов.
Секреты (GitHub): ANTHROPIC_API_KEY, CP_BOT_TOKEN (или TG_BOT_TOKEN), CP_OWNER_ID (или TG_CHAT_ID).
CP_DRY=1 — ничего не отправлять, только показать черновики."""
import os, re, json, html, random, datetime as dt, urllib.request, urllib.error, base64

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
BRANCH = 'channel'   # не 'state': state_sync.py пересобирает ту ветку одним force-push-коммитом и стирал очередь (09.11.2026)
CATS = {'news': 'ХАЙПОВАЯ НОВОСТЬ про рынки/трейдинг', 'smart': 'УМНАЯ МЫСЛЬ про трейдинг (механика рынка, риск, дисциплина)',
        'humor': 'СМЕШНОЕ про трейдинг (своя шутка/ситуация, не копия мема)', 'motiv': 'МОТИВАЦИЯ для развития и польза (конкретный совет/привычка)',
        'story': 'ИСТОРИЯ или РАЗБОР: короткий жизненный случай из трейдинга/рынка (типичная ошибка новичка, как сработал или не сработал приём, момент из истории рынка), в конце вопрос к читателям'}
MODE = os.environ.get('CP_MODE', '')   # urgent: проверка срочных новостей днём


def http(url, data=None, headers=None, method=None, timeout=40):
    h = {'User-Agent': 'Mozilla/5.0 (compatible; TradingPrideBot/1.0)'}; h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
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
    """Посты публичной страницы канала (последние ~20): [(views, text, when)]. Отсечку по давности делает collect (у юмора и обучения она шире, они пишут реже)."""
    out = []
    try:
        page = http('https://t.me/s/' + u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
    except Exception as e:
        print('  ! ' + u + ': ' + str(e)[:80]); return out
    for blk in page.split('tgme_widget_message_wrap')[1:]:
        m = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S)
        if not m: continue
        t = re.sub(r'<br\s*/?>', ' ', m.group(1)); t = re.sub(r'<[^>]+>', '', t); t = html.unescape(t)
        t = re.sub(r'https?://\S+|t\.me/\S+|@\w+', '', t); t = re.sub(r'\s+', ' ', t).strip()
        d = re.search(r'datetime="([^"]+)"', blk)
        try:
            when = dt.datetime.fromisoformat(d.group(1))
        except Exception:
            continue
        v = re.search(r'tgme_widget_message_views">([^<]+)<', blk)
        if len(t) > 40: out.append((views_num(v.group(1) if v else ''), t[:500], when))
    return out


POOL_OF = {'news': ['news', 'analysis'], 'humor': ['humor', 'smart'], 'smart': ['smart', 'edu', 'analysis'], 'motiv': ['edu', 'smart', 'analysis'], 'story': ['analysis', 'edu', 'smart']}
WIN_H = {'news': 36, 'analysis': 72, 'edu': 24 * 10, 'humor': 24 * 10, 'smart': 24 * 10}   # окно давности (часы) по рубрике канала


def collect():
    """Пулы сырья по рубрикам каналов: {'news': [(views, text, id)], 'humor': [...], ...}. Топ-5 свежих постов каждого канала; id = хеш текста, чтобы не брать одну идею дважды."""
    import hashlib
    now = dt.datetime.now(dt.timezone.utc); pools = {}
    for c in CH:
        got = [x for x in fetch(c['u']) if (now - x[2]).total_seconds() <= WIN_H.get(c['cat'], 36) * 3600]
        got = sorted(got, key=lambda x: x[0], reverse=True)[:5]
        print('  %-24s %-8s %d' % (c['u'], c['cat'], len(got)))
        for v, t, _ in got: pools.setdefault(c['cat'], []).append((v, t, hashlib.md5(t.encode()).hexdigest()[:10]))
    for k in pools: pools[k].sort(reverse=True)
    return pools


ONLY = os.environ.get('CP_ONLY', '')


def plan(today):
    """Утро (слот 10:00 МСК) = ВСЕГДА новость. Вечер (19:00) = по кругу смешное / умное / мотивация / история."""
    if ONLY in CATS: return [ONLY]
    if MODE == 'urgent': return ['news']
    rot = ['humor', 'smart', 'motiv', 'story']
    return ['news', rot[today.toordinal() % 4]]


def recent_topics():
    try: d, _ = load_drafts()
    except Exception: return ''
    xs = [v for v in sorted(d.values(), key=lambda v: v.get('ts', ''))[-10:] if v.get('status') != 'rejected' or not v.get('reason')]
    return '\n'.join('- ' + v['text'].split('\n')[0][:90] for v in xs[-8:])


def lessons():
    """Замечания владельца к отклонённым черновикам + удачные опубликованные: учим стиль."""
    try: d, _ = load_drafts()
    except Exception: return ''
    rej = [v for v in sorted(d.values(), key=lambda v: v.get('ts', ''))[-40:] if v.get('status') == 'rejected' and v.get('reason')][-8:]
    ok = [v for v in sorted(d.values(), key=lambda v: v.get('ts', ''))[-40:] if v.get('status') == 'published'][-2:]
    out = ''
    if rej: out += '\nЗАМЕЧАНИЯ ВЛАДЕЛЬЦА К ПРОШЛЫМ ЧЕРНОВИКАМ (обязательно учти, не повторяй ошибки):\n' + '\n'.join('- %s (было: «%s…»)' % (v['reason'], v['text'][:60].replace('\n', ' ')) for v in rej)
    if ok: out += '\nЭТИ ПОСТЫ ВЛАДЕЛЕЦ ОДОБРИЛ (ориентир по тону и длине, не копируй):\n' + '\n---\n'.join(v['text'] for v in ok)
    return out


def ask_llm(cats, rows, today, extra_add=''):
    extra = lessons() + extra_add
    wd = today.weekday()
    if 'news' in cats:
        extra += '\nНОВОСТЬ ДНЯ: ' + ('СРОЧНО. Пиши, только если есть действительно срочное мировое событие, о котором пишут минимум 3 источника или оно набрало взрывной охват и двигает форекс или индексы. Если такого нет, верни {"posts":[]}.' if MODE == 'urgent' else 'суббота: итоги недели на рынках и главное, что запомнилось.' if wd == 5 else 'воскресенье: что ждёт рынки на новой неделе (заседания ЦБ, ключевые данные, отчёты), только то, что есть в сырье, иначе общие ориентиры без выдуманных дат.' if wd == 6 else 'самая громкая мировая новость за ночь и утро.')
    seen = recent_topics()
    if seen: extra += '\nТЕМЫ, КОТОРЫЕ УЖЕ БЫЛИ В ПОСЛЕДНИЕ ДНИ (не повторяй, бери другое):\n' + seen
    src = '\n'.join('%d. %s' % (i + 1, t) for i, (v, t, _id) in enumerate(rows)) or '(источники сегодня пусты)'
    def q(i, c):   # живой вопрос к читателям: в историях всегда, в остальных примерно в каждом третьем посте
        return c == 'story' or (today.toordinal() + i) % 3 == 0
    want = '\n'.join('%d) %s%s' % (i + 1, CATS[c], ' [В КОНЦЕ ВОПРОС: ' + ('ответ смайлом-реакцией. Задай один конкретный вопрос из ситуации поста и сразу дай 2–3 варианта ответа смайлами, каждый со своим смыслом. Пример: «Было такое? 🔥 да, постоянно / 😅 пару раз / 😎 я по плану»' if True else 'ответ в комментариях (у канала есть группа обсуждения). Задай один конкретный вопрос из ситуации поста, на который легко ответить парой слов, и позови написать в комментариях естественно, без казёнщины. Пример: «а твой самый глупый слив какой был? расскажи в комментах»') + '. Не «а как вы думаете?»]' if q(i, c) else ' [без вопроса в конце]') for i, c in enumerate(cats))
    prompt = f"""Ты редактор телеграм-канала @trading_pride (трейдинг: форекс, индексы, акции; без крипты). Дата: {today}.
Ниже — свежие посты из популярных трейдинг-каналов. Для новости это факты дня. Для смешного и полезного это ИДЕИ: берёшь механику шутки или мысль и пишешь заново своими словами, со своим примером и деталями, не пересказывая предложение за предложением.
Напиши {len(cats)} ОРИГИНАЛЬНЫХ поста на русском:
{want}

ГЛАВНОЕ — ГОЛОС. Ты пишешь так, будто объясняешь другу-трейдеру в личке или за кофе. Просто, по-человечески, как говорят, а не как пишут. На «ты» или от «я/мы». Короткие рубленые фразы вперемешку с чуть более длинными. Можно сленг трейдеров (стоп, лонг, шорт, пробой, ложный пробой, депозит, слив) и лёгкую самоиронию. Есть мнение и эмоция: удивило, смешно, бесит, респект. Пиши как реально пишут сильные телеграм-каналы: цепляющая первая строка, дальше по делу, без вступлений.
ЖЁСТКИЕ ПРАВИЛА:
- Пиши с нуля своими словами. Источники — только сырьё: что обсуждают сегодня. Не повторяй их формулировки, шутки и порядок мысли.
- Новость: только мировые события, которые двигают ФОРЕКС и ИНДЕКСЫ (ФРС и другие ЦБ, макростатистика США/ЕС/Британии/Японии/Китая, нефть, золото, доллар, отчёты мегакомпаний, геополитика с реальным рыночным эффектом). Без крипты и локальной российской повестки. Источники бывают на английском: пересказывай факты по-русски своими словами. Бери тему, которая встречается в нескольких источниках или набрала много просмотров.
- Новость: только факты из сырья. Никаких выдуманных цифр, дат, имён. Не уверен — выбери другую тему или напиши «пишут, что…». В конце одна строка простыми словами, что это значит для трейдера, без прогноза цены.
- Никаких призывов купить/продать, гарантий, «сигналов», обещаний дохода. Без ссылок и @упоминаний, без названий чужих каналов.
- Смешное: возьми идею из сырья (приём шутки: ожидание против реальности, диалог, самоирония, сравнение с бытом) и сделай свою версию со свежей ситуацией. ЗАПРЕЩЕНО писать про то, что стоп выбило и цена ушла дальше, что закрыл раньше времени, что рынок охотится за моим стопом: это уже было много раз. Добрый юмор, без оскорблений.
- ФОРМАТ: 250–600 символов. Первая строка — крючок до 70 символов с одним эмодзи в начале. Дальше 2–4 короткие строки. Эмодзи по смыслу в начале ключевых строк, всего 3–6, без перебора. Никакой разметки (звёздочки, markdown, HTML).
ЗАПРЕЩЕНО (так пишут нейросети, это сразу выдаёт текст):
- Конструкции «не X, а Y», «это не просто X, это Y», «дело не в X».
- Длинные и короткие тире (— и –). Вместо них точка, запятая, двоеточие или скобки.
- Перечисления ровно из трёх пунктов ради красоты.
- Однострочные «выводы» в конце типа «вот что важно», «и это меняет всё», «вывод простой».
- Канцелярит и пафос: «ключевой», «важно отметить», «в современном мире», «давайте разберёмся», «стоит обратить внимание», «играет важную роль», «на фоне», «в условиях».
- Обращение «друзья», «коллеги», «дорогие трейдеры», и дежурные вопросы вроде «а как вы думаете?», «что скажете?». Вопрос в конце бывает только там, где это указано у поста, он про конкретную ситуацию.
- Заголовок-крючок в стиле «Всё, что нужно знать о…».
Примеры тона (свои, не копируй дословно):
  Новость: «🏦 ФРС опять никуда не торопится\nСтавку оставили как есть, и доллар сначала дёрнулся вниз, а потом вернулся обратно. Powell сказал, что ждёт ещё данных по инфляции. Для нас это значит: на ближайших свечах будет шумно, но направление пока не выбрано.»
  Смешное: «😅 Поставил стоп. Цена подошла, выбила, развернулась и улетела без меня\nЗнакомо? Рынок как будто читает мой терминал. Утешаю себя тем, что хоть депозит остался при мне.»
- Для КАЖДОГО поста добавь "media": {{"type":"photo|video|gif|card","query":"2–4 слова НА АНГЛИЙСКОМ для поиска подходящего бесплатного фото/видео/гифки (например: stock market screen, trader stress, gold bars, oil rig, success sunrise)"}}. Новости и умное: photo или video. Смешное: gif. Мотивация: photo или video. Не уверен: card. Запрос к стоку делай КОНКРЕТНЫМ и непохожим на прошлые (список ниже), предмет или сцена, а не общие слова trading или chart.
- Для КАЖДОГО поста добавь "card": надпись для запасной картинки: "title" (2–6 слов, без эмодзи, суть) и "sub" (до 6 слов, можно пусто).
Верни ТОЛЬКО JSON: {{"posts":[{{"cat":"news|smart|humor|motiv|story","text":"...","media":{{"type":"..","query":".."}},"card":{{"title":"...","sub":"..."}}}}]}} — ровно {len(cats)} поста в том же порядке. Для смешного, умного, мотивации и истории добавь в пост поле "src": номер выбранной идеи из СЫРЬЯ (число).

{extra}

СЫРЬЁ:
{src}"""
    body = json.dumps({'model': MODEL, 'max_tokens': 3000, 'messages': [{'role': 'user', 'content': prompt}]}).encode()
    resp = json.loads(http('https://api.anthropic.com/v1/messages', body, {'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}, 'POST', 120))
    txt = ''.join(b.get('text', '') for b in resp.get('content', []))
    j = json.loads(txt[txt.find('{'):txt.rfind('}') + 1])
    return j.get('posts', [])


BAD = re.compile(r'https?://|t\.me|@\w|гарантир|100\s*%\s*прибыл|купи(те)?\b|продавай|[—–]|не\s+просто|важно отметить|ключев|давайте|друзья|коллеги|в современном|играет важную|обратить внимание|не\s+[^.!?\n]{1,40},\s*а\s|[Ээ]то\s+не\s+[^.!?\n]{1,50}[.!]\s*(Это|Это\s+—)|не\s+[^.!?\n]{1,50}[.!]\s*[А-ЯЁ][а-яё]+\s+(это|просто|единственн)', re.I)


def valid(p):
    t = p.get('text', '')
    return p.get('cat') in CATS and 200 <= len(t) <= 800 and not BAD.search(t) and sum(1 for ch in t if ord(ch) > 0x2000) >= 2 and 2 <= len((p.get('card') or {}).get('title', '')) <= 60


FMT = {
    'news': ['главная новость, реакция рынка, что смотреть дальше', 'цифры против прогноза: что вышло и что ждали', 'кто выиграл и кто проиграл на этой новости', 'что случилось, почему, какие инструменты заденет', 'коротко и сухо: факт, цифра, одна мысль', 'контекст: что было раньше и чем это отличается от прошлых раз'],
    'humor': ['ожидание и реальность', 'диалог трейдера с самим собой', 'виды трейдеров по поведению', 'совет наоборот (сарказм)', 'сравнение трейдинга с бытовой ситуацией (кухня, пробки, спортзал)', 'мини-история из трёх строк с неожиданной концовкой', 'если бы рынок был человеком', 'мысли в понедельник утром, в пятницу вечером', 'подборка из 4 коротких шуток-наблюдений'],
    'smart': ['термин простыми словами с примером', 'частая ошибка и как её исправить', 'одна цифра или факт и что из него следует', 'правило из практики с коротким примером', 'мини-чек-лист из 4–5 пунктов', 'вопрос новичка и ответ на него', 'как читать одну конкретную вещь на графике или в календаре'],
    'motiv': ['история известного трейдера или инвестора (только проверяемые факты, без выдуманных цитат)', 'привычка недели, которую легко начать', 'как вести журнал сделок и что в нём смотреть', 'про терпение и дисциплину на примере из обычной жизни', 'как пережить серию неудач, не ломая план', 'итоги недели: что стоит проверить в своей торговле'],
    'story': ['случай из истории рынка (только известные факты)', 'типичная ошибка новичка и чем она закончилась', 'как работает один рыночный механизм на живом примере'],
}
NEWS_AREAS = ['ЦБ и ставки', 'макроданные (инфляция, занятость, ВВП, продажи)', 'отчёты и новости мегакомпаний', 'нефть и энергетика', 'золото и металлы', 'доллар, евро, фунт, иена', 'геополитика с реальным эффектом на рынки', 'итоги дня на рынке акций США или Европы', 'Азия и Китай', 'что выходит на этой неделе (календарь)']
STOP_RE = re.compile(r'стоп|выбил|выбива', re.I)
OLD_STORY_BAD = re.compile(r'выбил[аио]?\b|выбива|охот\w+ за (моим )?стоп|закрыл\w* раньше|раньше времени|снял\w* мой стоп', re.I)


def _words(t):
    return set(w for w in re.findall(r'[а-яёa-z0-9]{5,}', t.lower()))


def similar(t, recent, th=0.28):
    a = _words(t)
    for r in recent:
        b = _words(r)
        if a and b and len(a & b) / len(a | b) >= th: return True
    return False


def valid_ctx(p, recent_all, recent_nonnews):
    """valid + не похоже на последние посты + запрет на заезженные сюжеты (стоп выбило, закрыл раньше) в смешном и полезном."""
    if not valid(p): return False
    t = p.get('text', '')
    if similar(t, recent_all): print('  ~ похоже на недавний пост, пропуск'); return False
    if p.get('cat') != 'news':
        if OLD_STORY_BAD.search(t): print('  ~ заезженный сюжет про стоп, пропуск'); return False
        if sum(1 for x in recent_nonnews[-8:] if STOP_RE.search(x)) >= 2 and STOP_RE.search(t): print('  ~ про стоп уже было, пропуск'); return False
    return True


def variety_extra(cat, drafts, pools, used_src):
    """Подсказки на разнообразие: формат подачи, область темы, запрещённые эмодзи-начала, прошлые запросы к стоку."""
    ds = sorted(drafts.values(), key=lambda v: v.get('ts', ''))
    same = [v for v in ds if v.get('cat') == cat][-8:]
    recent_fmt = set(v.get('fmt') for v in same[-5:])
    fm = [f for f in FMT.get(cat, []) if f not in recent_fmt] or FMT.get(cat, [])
    fmt = random.choice(fm) if fm else ''
    out = ''
    if fmt: out += '\nФОРМАТ ЭТОГО ПОСТА (держись его): ' + fmt + '.'
    firsts = [v['text'].split('\n')[0][:2].strip() for v in same[-5:] if v.get('text')]
    if firsts: out += '\nПЕРВЫЙ ЭМОДЗИ НЕ БРАТЬ ИЗ: ' + ' '.join(firsts) + ' (выбери другой по смыслу).'
    if cat == 'news':
        seen = ' | '.join(v['text'].split('\n')[0][:60] for v in same[-6:])
        out += '\nОБЛАСТЬ ТЕМЫ выбери ТУ, которой не было в последних новостях (' + seen + '). Варианты: ' + '; '.join(NEWS_AREAS) + '. Не пиши снова про Nvidia, нефть и Иран, если они были в последних трёх новостях. Концовку вида «Для нас это значит» используй не в каждой новости: допустимы «что смотреть дальше», «кого заденет», короткая ирония, просто факт без вывода.'
    else:
        out += '\nНЕ ПОВТОРЯЙ тему и сюжет последних постов этой рубрики: ' + ' | '.join(v['text'].split('\n')[0][:60] for v in same[-6:]) + '. ЗАПРЕЩЕНО про то, что стоп выбило / закрыл раньше времени / рынок охотится за стопом.'
    qs = [v.get('mq') for v in ds[-14:] if v.get('mq')]
    if qs: out += '\nЗАПРОСЫ К СТОКУ, КОТОРЫЕ УЖЕ БЫЛИ (не повторяй, придумай другой предмет или сцену): ' + '; '.join(qs) + '.'
    return out, fmt


FAILED = []   # (рубрика, причина) для сообщения владельцу


def gen_posts(cats, pools, today):
    """По одному запросу к модели на пост (до 4 попыток каждый): сырьё своей рубрики, формат, проверка на похожесть. Недостающее потом дозаказывает будильник канала."""
    try: drafts, _ = load_drafts()
    except Exception: drafts = {}
    ds = sorted(drafts.values(), key=lambda v: v.get('ts', ''))
    recent_all = [v['text'] for v in ds[-16:]]; recent_nn = [v['text'] for v in ds if v.get('cat') != 'news'][-10:]
    used_src = set(v.get('src_id') for v in drafts.values() if v.get('src_id'))
    out = []
    for c in cats:
        cand = [x for k in POOL_OF.get(c, ['news']) for x in pools.get(k, []) if x[2] not in used_src]
        top = cand[:14]; random.shuffle(top); rows = top[:8] if c != 'news' else cand[:45]
        add, fmt = variety_extra(c, drafts, pools, used_src)
        got = None; soft = None; why = []
        for att in range(4):
            r = [p for p in ask_llm([c], rows, today, add)]
            if not r: why.append('модель вернула пустой ответ'); print('  попытка %d для %s: пустой ответ' % (att + 1, c)); continue
            cand0 = dict(r[0]); cand0['cat'] = c   # рубрику задаёт план, а не ответ модели (для story модель отвечала smart/motiv и пост терялся)
            if valid_ctx(cand0, recent_all, recent_nn): got = cand0; break
            if valid(cand0) and soft is None: soft = cand0
            why.append('жёсткая проверка' if not valid(cand0) else 'похож на прошлые или заезженный сюжет')
            print('  попытка %d для %s не прошла (%s)' % (att + 1, c, why[-1]))
        if not got and soft:
            got = soft; got['soft'] = True; print('  беру запасной вариант для %s: прошёл жёсткую проверку, но похож на прошлые посты' % c)
        if not got: FAILED.append((c, ', '.join(sorted(set(why))) or 'нет ответа'))
        if got:
            got['fmt'] = fmt
            try:
                si = int(got.get('src', 0))
                if c != 'news' and 1 <= si <= len(rows): got['src_id'] = rows[si - 1][2]
            except Exception: pass
            out.append(got); recent_all.append(got['text'])
    return out


PALETTE = {'news': ((10, 25, 60), (30, 90, 200), 'НОВОСТИ РЫНКА'), 'smart': ((20, 20, 40), (90, 50, 160), 'ТРЕЙДЕРУ НА ЗАМЕТКУ'),
           'humor': ((70, 30, 10), (230, 120, 30), 'ТРЕЙДЕРСКИЙ ЮМОР'), 'motiv': ((6, 50, 45), (20, 160, 120), 'РОСТ И ДИСЦИПЛИНА')}


def add_logo(img, width_frac=0.16, margin_frac=0.035, opacity=0.92):
    """Логотип Trading Pride в правом нижнем углу карточки (report_assets/logo.png), с лёгкой тенью. Если файла нет, карточка остаётся без логотипа."""
    from PIL import Image, ImageFilter
    try:
        lg = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'report_assets', 'logo.png')).convert('RGBA')
        lg = lg.crop(lg.split()[3].getbbox())
    except Exception:
        return img
    img = img.convert('RGBA'); W, H = img.size
    w = int(W * width_frac); h = int(lg.height * w / lg.width); lg = lg.resize((w, h), Image.LANCZOS)
    lg.putalpha(lg.split()[3].point(lambda v: int(v * opacity)))
    m = int(W * margin_frac); x = W - w - m; y = H - h - m
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); blk = Image.new('RGBA', lg.size, (0, 0, 0, 255))
    blk.putalpha(lg.split()[3].point(lambda v: int(v * 0.55))); sh.paste(blk, (x + 2, y + 3)); sh = sh.filter(ImageFilter.GaussianBlur(5))
    img = Image.alpha_composite(img, sh); img.alpha_composite(lg, (x, y))
    return img.convert('RGB')


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
    img = add_logo(img)
    img.save(path, 'PNG')


PIXABAY = os.environ.get('PIXABAY_KEY', ''); PEXELS = os.environ.get('PEXELS_KEY', ''); GIPHY = os.environ.get('GIPHY_KEY', '')


def find_media(m, cat, used=None, v=0):
    """Лицензионные площадки: Pexels (фото/видео, свободная лицензия) и Giphy API. Нет ключа/результата -> None (будет карточка)."""
    import urllib.parse
    used = used if used is not None else set()   # 20.11.2026: адреса уже использованных картинок/видео/GIF — не повторять; v — номер замены (другая страница выдачи)
    typ, q = (m or {}).get('type', 'card'), urllib.parse.quote((m or {}).get('query', '') or 'trading')
    pg = 1 + (v % 4)
    try:
        if typ == 'gif' and GIPHY:
            r = []
            for qq in (q, urllib.parse.quote(urllib.parse.unquote(q).split()[0]), 'trading', 'money'):
                r = json.loads(http('https://api.giphy.com/v1/gifs/search?api_key=%s&q=%s&limit=25&offset=%d&rating=pg-13&lang=en' % (GIPHY, qq, 25 * (v % 4))))['data']
                r = [g for g in r if (g['images'].get('downsized_large', {}).get('url') or g['images']['original']['url']) not in used]
                if r: break
            random.shuffle(r)
            for g in r:
                u = g['images'].get('downsized_large', {}).get('url') or g['images']['original']['url']
                if int(g['images'].get('downsized_large', {}).get('size', 0) or 0) < 15000000: return ('animation', u)
        if typ == 'video' and PIXABAY:
            hv = json.loads(http('https://pixabay.com/api/videos/?key=%s&q=%s&per_page=20&page=%d&safesearch=true' % (PIXABAY, q, pg)))['hits']
            random.shuffle(hv)
            for vv in hv:
                if vv.get('duration', 99) > 25: continue
                mm = vv['videos'].get('medium') or vv['videos'].get('small')
                if mm and mm.get('size', 0) < 18000000 and mm['url'] not in used: return ('video', mm['url'])
        if typ in ('photo', 'video') and PIXABAY:
            h = json.loads(http('https://pixabay.com/api/?key=%s&q=%s&image_type=photo&orientation=horizontal&safesearch=true&per_page=30&page=%d' % (PIXABAY, q, pg)))['hits']
            h = [x for x in h if x['largeImageURL'] not in used]
            if h: return ('photo', random.choice(h)['largeImageURL'])
        if typ == 'video' and PEXELS:
            r = json.loads(http('https://api.pexels.com/videos/search?query=%s&per_page=8&size=medium&orientation=landscape' % q, headers={'Authorization': PEXELS}))['videos']
            for vv in r:
                if vv.get('duration', 99) > 25: continue
                fs = [f for f in vv['video_files'] if f.get('file_type') == 'video/mp4' and 600 <= (f.get('width') or 0) <= 1300]
                if fs and sorted(fs, key=lambda f: f['width'])[-1]['link'] not in used: return ('video', sorted(fs, key=lambda f: f['width'])[-1]['link'])
        if typ in ('photo', 'video') and PEXELS:
            r = json.loads(http('https://api.pexels.com/v1/search?query=%s&per_page=30&page=%d&orientation=landscape' % (q, pg), headers={'Authorization': PEXELS}))['photos']
            r = [x for x in r if x['src']['large'] not in used]
            if r: return ('photo', random.choice(r)['src']['large'])
    except Exception as e:
        print('! медиа не найдено:', str(e)[:100])
    return None


def http_bytes(url, timeout=40):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; TradingPrideBot/1.0)'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def logo_photo(url):
    """Скачивает стоковое фото, ставит логотип и возвращает путь к файлу; при любой ошибке None (тогда фото уходит как раньше, по ссылке)."""
    try:
        import io, hashlib
        from PIL import Image
        img = Image.open(io.BytesIO(http_bytes(url))).convert('RGB')
        if img.width > 1600: img = img.resize((1600, int(img.height * 1600 / img.width)))
        path = '/tmp/lp_%s.jpg' % hashlib.md5(url.encode()).hexdigest()[:10]
        add_logo(img, 0.15).save(path, 'JPEG', quality=90)
        return path
    except Exception as e:
        print('! логотип на фото не поставился, фото без логотипа:', str(e)[:100]); return None


def edit_photo_file(chat, mid, path, caption, kb):
    import uuid
    bd = uuid.uuid4().hex; parts = []
    def fld(n, v): parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (bd, n, v)).encode())
    fld('chat_id', chat); fld('message_id', mid); fld('reply_markup', json.dumps(kb))
    fld('media', json.dumps({'type': 'photo', 'media': 'attach://f', 'caption': caption[:1024], 'parse_mode': 'HTML'}))
    parts.append(('--%s\r\nContent-Disposition: form-data; name="f"; filename="p.jpg"\r\nContent-Type: image/jpeg\r\n\r\n' % bd).encode() + open(path, 'rb').read() + b'\r\n')
    parts.append(('--%s--\r\n' % bd).encode())
    return json.loads(http('https://api.telegram.org/bot%s/editMessageMedia' % TOKEN, b''.join(parts), {'Content-Type': 'multipart/form-data; boundary=' + bd}, 'POST', 60))


def send_url_media(chat, kind, url, caption, kb):
    if kind == 'photo':
        lp = logo_photo(url)
        if lp: return send_photo(chat, lp, caption, kb)['result']['photo'][-1]['file_id']
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


def used_media(drafts):
    return set(x['murl'] for x in drafts.values() if x.get('murl'))


def llm_media(text):
    """Для старых черновиков без запроса к стоку: просим у модели 2–4 английских слова для поиска картинки."""
    if not API_KEY: return None
    try:
        body = json.dumps({'model': MODEL, 'max_tokens': 80, 'messages': [{'role': 'user', 'content': 'Пост для телеграм-канала про трейдинг:\n' + text[:700] + '\n\nДай запрос для поиска подходящей бесплатной картинки на стоке: 2–4 слова на английском, конкретные предметы или сцена, без слов trading/chart/forex в каждом запросе. Ответ только JSON: {"type":"photo","query":"..."}'}]}).encode()
        r = json.loads(http('https://api.anthropic.com/v1/messages', body, {'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'}, 'POST', 60))
        m = re.search(r'\{.*\}', r['content'][0]['text'], re.S)
        return json.loads(m.group(0)) if m else None
    except Exception as e:
        print('! запрос к модели за поисковой фразой не вышел:', str(e)[:100]); return None


def swap_media():
    """20.11.2026: «🖼 Другая картинка» / «Картинка не подходит» меняет ТОЛЬКО медиа в черновике (текст и статус «ждёт решения» остаются)."""
    did, chat, mid = os.environ.get('CP_SWAP', ''), os.environ.get('CP_CHAT', ''), os.environ.get('CP_MID', '')
    drafts, sha = load_drafts(); d = drafts.get(did)
    if not d: print('Черновик не найден:', did); return
    n = int(d.get('nsw', 0)) + 1; d['nsw'] = n
    base = {'type': d.get('mt') or 'photo', 'query': d.get('mq') or ''}
    if not base['query']:
        g = llm_media(d['text']); base = g or {'type': 'photo', 'query': {'news': 'stock market', 'smart': 'business strategy', 'humor': 'funny office', 'motiv': 'sunrise mountain', 'story': 'city night'}.get(d['cat'], 'finance')}
        d['mq'], d['mt'] = base['query'], base.get('type', 'photo')
    used = used_media(drafts); words = base['query'].split()
    variants = [base['query'], ' '.join(words[:2]) or base['query'], (base['query'] + ' ' + ['business', 'city', 'money', 'screen'][n % 4]).strip(), {'news': 'stock market', 'smart': 'business', 'humor': 'funny', 'motiv': 'success', 'story': 'city'}.get(d['cat'], 'finance')]
    got = None
    for qv in variants:
        got = find_media({'type': base.get('type', 'photo'), 'query': qv}, d['cat'], used, n)
        if got: break
    if not got:
        for qv in variants:   # если нужного вида нет, пробуем обычное фото
            got = find_media({'type': 'photo', 'query': qv}, d['cat'], used, n)
            if got: break
    kb = {'inline_keyboard': [[{'text': '✅ Опубликовать' + (' · утро 10:00' if d['cat'] == 'news' else ' · вечер 19:00'), 'callback_data': 'ap:' + did}], [{'text': '🖼 Другая картинка', 'callback_data': 'pc:' + did}, {'text': '❌ Отклонить', 'callback_data': 'rj:' + did}]]}
    if not got:
        tg('editMessageReplyMarkup', {'chat_id': chat, 'message_id': int(mid), 'reply_markup': kb})
        tg('sendMessage', {'chat_id': chat, 'text': 'Не нашёл новую картинку (сток ничего не вернул). Попробуй ещё раз позже.'}); save_drafts(drafts, sha); return
    kind, url = got
    med = {'type': {'photo': 'photo', 'video': 'video', 'animation': 'animation'}[kind], 'media': url, 'caption': html_text(d['text'])[:1024], 'parse_mode': 'HTML'}
    lp = logo_photo(url) if kind == 'photo' else None
    r = edit_photo_file(chat, int(mid), lp, html_text(d['text']), kb) if lp else tg('editMessageMedia', {'chat_id': chat, 'message_id': int(mid), 'media': med, 'reply_markup': kb})
    if r.get('ok'):
        res = r['result']; d['photo'] = res['photo'][-1]['file_id'] if res.get('photo') else (res.get('animation') or res.get('video') or {}).get('file_id', d.get('photo'))
    else:
        print('! editMessageMedia не вышло:', str(r)[:200])   # запасной путь: новое сообщение с новой картинкой, старое остаётся выше
        d['photo'] = send_url_media(chat, kind, url, html_text(d['text']), kb)
    d['kind'] = kind; d['murl'] = url; d['status'] = 'pending'
    save_drafts(drafts, sha); print('Картинка заменена:', did, kind, url[:80])


def main():
    if os.environ.get('CP_SWAP'):
        try: return swap_media()
        except Exception as e:   # не оставляем на кнопках «⏳ Ищу…»: возвращаем обычные кнопки и сообщаем
            print('! замена картинки упала:', repr(e)[:200])
            did, chat, mid = os.environ.get('CP_SWAP', ''), os.environ.get('CP_CHAT', ''), os.environ.get('CP_MID', '')
            try:
                tg('editMessageReplyMarkup', {'chat_id': chat, 'message_id': int(mid), 'reply_markup': {'inline_keyboard': [[{'text': '✅ Опубликовать', 'callback_data': 'ap:' + did}], [{'text': '🖼 Другая картинка', 'callback_data': 'pc:' + did}, {'text': '❌ Отклонить', 'callback_data': 'rj:' + did}]]}})
                tg('sendMessage', {'chat_id': chat, 'text': 'Не получилось заменить картинку (%s). Нажми «🖼 Другая картинка» ещё раз.' % repr(e)[:100]})
            except Exception: pass
            raise SystemExit(1)
    today = dt.datetime.now(dt.timezone.utc).date()
    if MODE != 'urgent' and os.environ.get('GITHUB_EVENT_NAME') == 'schedule':
        dd, _ = load_drafts()   # запоздавший запуск по расписанию (или после будильника /api/chtick): сегодняшние черновики уже есть — не дублировать
        if any(not v.get('urgent') and v.get('ts', '')[:10] == today.isoformat() for v in dd.values()): print('Черновики за сегодня уже есть'); return
    print('Читаю каналы:'); pools = collect()
    cats = plan(today); print('План:', cats, '· сырья по рубрикам:', {k: len(v) for k, v in pools.items()})
    posts = []; ask_ok = True
    if API_KEY:
        try:
            posts = gen_posts(cats, pools, today)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:300]
            print('Ошибка API Anthropic:', e.code, body)
            hint = 'Пополните баланс на console.anthropic.com → Billing.' if 'credit' in body.lower() or e.code in (400, 402) else 'Проверьте ключ ANTHROPIC_API_KEY.'
            if TOKEN and OWNER and not DRY:
                try: tg('sendMessage', {'chat_id': OWNER, 'text': 'Автопостинг: не удалось написать черновики (код %s). %s' % (e.code, hint)})
                except Exception: pass
            return
        except Exception as e:
            print('Ошибка при написании постов:', repr(e)[:300])
            if TOKEN and OWNER and not DRY:
                try: tg('sendMessage', {'chat_id': OWNER, 'text': 'Автопостинг: сбой при написании постов (%s). Напишу в чат Claude, исправлю.' % repr(e)[:150]})
                except Exception: pass
            raise SystemExit(1)
    else:
        print('НЕТ ANTHROPIC_API_KEY — черновики не сгенерированы')
    if MODE == 'urgent' and not posts: print('Срочного нет'); return
    if not posts:
        print('Нет годных черновиков — выходим')
        if TOKEN and OWNER and not DRY and MODE != 'urgent':
            try: tg('sendMessage', {'chat_id': OWNER, 'text': 'Автопостинг: черновик не получился (%s). Будильник попробует ещё раз; если не выйдет, напиши в чат Claude.' % '; '.join('%s: %s' % x for x in FAILED)[:200]})
            except Exception: pass
        return
    for p in posts: print('\n--- %s ---\n%s' % (p['cat'], p['text']))
    if DRY: print('\nCP_DRY=1: ничего не отправлено'); return
    if not (TOKEN and OWNER): print('НЕТ CP_BOT_TOKEN/CP_OWNER_ID'); return
    drafts, sha = load_drafts()
    if MODE == 'urgent' and any(v.get('urgent') and v.get('ts', '')[:10] == today.isoformat() for v in drafts.values()): print('Срочная за сегодня уже была'); return
    used = used_media(drafts)
    for i, p in enumerate(posts):
        did = '%s-%s' % (today.strftime('%Y%m%d'), ('u%d' % (i + 1)) if MODE == 'urgent' else ('1' if p['cat'] == 'news' else '2'))
        drafts[did] = {'cat': p['cat'], 'text': p['text'], 'status': 'pending', 'urgent': MODE == 'urgent', 'ts': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}
        kb = {'inline_keyboard': [[{'text': '✅ Опубликовать' + (' · утро 10:00' if p['cat'] == 'news' else ' · вечер 19:00'), 'callback_data': 'ap:' + did}], [{'text': '🖼 Другая картинка', 'callback_data': 'pc:' + did}, {'text': '❌ Отклонить', 'callback_data': 'rj:' + did}]]}
        try:
            drafts[did]['mq'] = (p.get('media') or {}).get('query', ''); drafts[did]['mt'] = (p.get('media') or {}).get('type', 'photo'); drafts[did]['fmt'] = p.get('fmt', ''); drafts[did]['src_id'] = p.get('src_id', '')
            got = find_media(p.get('media'), p['cat'], used)
            if got:
                try:
                    drafts[did]['photo'] = send_url_media(OWNER, got[0], got[1], html_text(p['text']), kb); drafts[did]['kind'] = got[0]; drafts[did]['murl'] = got[1]; used.add(got[1])
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
    try: tg('sendMessage', {'chat_id': OWNER, 'text': ('🚨 Срочная новость. Если хочешь выпустить сразу, нажми «Опубликовать», затем «▶️ Сейчас».' if MODE == 'urgent' else '✅ Готово: %d черновика выше. Нажми «Опубликовать» или «Отклонить» под каждым.' % len(posts))})
    except Exception: pass
    print('Отправлено на одобрение:', len(posts))


if __name__ == '__main__':
    main()
