// Бот-редактор канала @trading_pride (01.11.2026): меню, черновики на одобрение, отчёты и статистика по запросу.
// Черновики: ветка `state`, channel/drafts.json (создаёт channel_poster/run.py в GitHub Actions).
// Окружение Vercel: CP_BOT_TOKEN, CP_OWNER_ID (команды и кнопки принимаются только от владельца), CP_CHANNEL, CP_WEBHOOK_SECRET, GH_TOKEN.
// Один раз: /api/tgbot?setup=1&k=<ключ Пульта> — регистрирует веб-хук, команды и описание бота.
import { keyOk } from '../../lib/auth';
import { readJson, writeJson } from '../../lib/gh';

const TOK = () => process.env.CP_BOT_TOKEN || '';
const CHANNEL = () => process.env.CP_CHANNEL || '@trading_pride';
const tg = (m, body) => fetch(`https://api.telegram.org/bot${TOK()}/${m}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then((r) => r.json());
const CAT = { news: '📰 Новости', smart: '🧠 Умное', humor: '😄 Смешное', motiv: '🚀 Мотивация' };
const ST = { pending: '⏳ ждёт решения', published: '✅ опубликован', rejected: '❌ отклонён', scheduled: '🕒 запланирован' };

const MENU = { inline_keyboard: [
  [{ text: '📝 Черновики', callback_data: 'm:drafts' }, { text: '📊 Статистика', callback_data: 'm:stats' }],
  [{ text: '🗓 Отчёт за неделю', callback_data: 'm:week' }, { text: '⚡ Пост сейчас', callback_data: 'm:gen' }],
  [{ text: '📚 Источники', callback_data: 'm:src' }, { text: 'ℹ️ Помощь', callback_data: 'm:help' }],
] };
const BACK = { inline_keyboard: [[{ text: '⬅️ В меню', callback_data: 'm:menu' }]] };

const HELP = 'Бот-редактор канала @trading_pride.\n\nКаждый день я готовлю 1–2 оригинальных поста (новости рынков, умное, смешное, мотивация) и присылаю вам на одобрение. В канал уходит только то, что вы подтвердили кнопкой.\n\nКоманды:\n/menu — главное меню\n/drafts — черновики, ждущие решения\n/stats — статистика за 30 дней\n/week — отчёт за неделю\n/gen — запросить новые черновики сейчас\n/sources — каналы-источники тем\n/help — эта справка';

function dayOf(id) { const s = String(id).slice(0, 8); return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`; }
function inRange(id, days) { const d = Date.parse(dayOf(id) + 'T00:00:00Z'); return isFinite(d) && Date.now() - d <= days * 86400000 + 86400000; }
function tally(data, days) {
  const t = { published: 0, rejected: 0, pending: 0, cats: {} };
  Object.keys(data || {}).forEach((id) => {
    if (!inRange(id, days)) return;
    const d = data[id]; t[d.status] = (t[d.status] || 0) + 1;
    const c = (t.cats[d.cat] = t.cats[d.cat] || { published: 0, rejected: 0, pending: 0 }); c[d.status] = (c[d.status] || 0) + 1;
  });
  return t;
}
function statsText(data, days, title, subs) {
  const t = tally(data, days), total = t.published + t.rejected + t.pending, dec = t.published + t.rejected;
  let s = `📊 ${title}\n\n`;
  if (subs) s += `Подписчиков в канале: ${subs}\n`;
  s += `Черновиков: ${total}\n✅ Опубликовано: ${t.published}\n❌ Отклонено: ${t.rejected}\n⏳ Ждут решения: ${t.pending}\n`;
  if (dec) s += `Доля одобренных: ${Math.round((100 * t.published) / dec)}%\n`;
  const keys = Object.keys(CAT).filter((k) => t.cats[k]);
  if (keys.length) { s += '\nПо рубрикам:\n'; keys.forEach((k) => { const c = t.cats[k]; s += `${CAT[k]}: ${c.published || 0} опубл. · ${c.rejected || 0} откл.${c.pending ? ' · ' + c.pending + ' ждёт' : ''}\n`; }); }
  if (!total) s += '\nЗа этот период черновиков не было.';
  return s;
}
async function subsCount() { try { const r = await tg('getChatMemberCount', { chat_id: CHANNEL() }); return r.ok ? r.result : null; } catch (e) { return null; } }
const MK = { photo: ['sendPhoto', 'photo'], video: ['sendVideo', 'video'], animation: ['sendAnimation', 'animation'] };
const REASONS = { none: 'Без причины', ai: 'Звучит как ИИ', facts: 'Неточные факты', topic: 'Не по теме', long: 'Слишком длинно', pic: 'Картинка не подходит' };
// Слоты публикации по МСК: 10:00 и 19:00 (UTC 07:00 и 16:00). Берём ближайший свободный.
const SLOTS_UTC = [7, 16];
function nextSlot(data, cat) {
  const hours = cat === 'news' ? SLOTS_UTC : [16];   // новости: любой ближайший слот; остальное только вечером 19:00
  const taken = new Set(Object.values(data || {}).filter((x) => x.status === 'scheduled' && x.at).map((x) => x.at));
  const now = Date.now() + 10 * 60000;
  for (let day = 0; day < 6; day++) for (const h of hours) {
    const t = new Date(); t.setUTCDate(t.getUTCDate() + day); t.setUTCHours(h, 0, 0, 0);
    const iso = t.toISOString();
    if (t.getTime() > now && !taken.has(iso)) return iso;
  }
}
function slotLabel(iso) {
  const f = (d, o) => new Date(d).toLocaleDateString('ru-RU', { timeZone: 'Europe/Moscow', ...o });
  const day = f(iso, {}) === f(Date.now(), {}) ? 'сегодня' : f(iso, {}) === f(Date.now() + 864e5, {}) ? 'завтра' : f(iso, { day: 'numeric', month: 'long' });
  return day + ' в ' + new Date(iso).toLocaleTimeString('ru-RU', { timeZone: 'Europe/Moscow', hour: '2-digit', minute: '2-digit' }) + ' МСК';
}
const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const htmlText = (t) => { const i = t.indexOf('\n'); return i < 0 ? '<b>' + esc(t) + '</b>' : '<b>' + esc(t.slice(0, i)) + '</b>' + esc(t.slice(i)); };
async function send(chat, text, kb) { return tg('sendMessage', { chat_id: chat, text: text.slice(0, 4000), reply_markup: kb || MENU }); }

async function showDrafts(chat, data) {
  const pend = Object.keys(data || {}).filter((id) => data[id].status === 'pending').sort();
  if (!pend.length) return send(chat, '📝 Черновиков, ждущих решения, нет.\n\nНовые приходят ежедневно утром. Можно запросить сейчас: /gen');
  for (const id of pend) {
    const kb = { inline_keyboard: [[{ text: '✅ Опубликовать', callback_data: 'ap:' + id }, { text: '❌ Отклонить', callback_data: 'rj:' + id }]] };
    if (data[id].photo) await tg((MK[data[id].kind] || MK.photo)[0], { chat_id: chat, [(MK[data[id].kind] || MK.photo)[1]]: data[id].photo, caption: htmlText(data[id].text).slice(0, 1024), parse_mode: 'HTML', reply_markup: kb });
    else await tg('sendMessage', { chat_id: chat, text: `Черновик ${id} · ${CAT[data[id].cat] || data[id].cat}\n\n${data[id].text}`.slice(0, 4000), reply_markup: kb });
  }
}
async function showSources(chat) {
  const { data } = await readJson('channel_poster/sources.json', {}, 'main');
  const ch = (data && data.channels) || [];
  const groups = { news: '📰 Новости', analysis: '🔎 Аналитика', edu: '🎓 Обучение', humor: '😄 Юмор' };
  let s = `📚 Каналы-источники тем (${ch.length})\nТексты не копируются: из них берутся только темы и факты.\n`;
  Object.keys(groups).forEach((g) => { const l = ch.filter((c) => c.cat === g); if (l.length) s += `\n${groups[g]}\n` + l.map((c) => `• @${c.u}${c.reach_pct ? ' · охват ' + c.reach_pct + '%' : ''}`).join('\n') + '\n'; });
  return send(chat, s, BACK);
}
async function generate(chat, only) {
  const repo = process.env.GH_REPO || 'turop0001/Trading-Pride';
  const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/channel_posts.yml/dispatches`, { method: 'POST',
    headers: { Authorization: `Bearer ${process.env.GH_TOKEN}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' }, body: JSON.stringify({ ref: 'main', inputs: only ? { dry: '0', cat: only } : { dry: '0' } }) });
  return send(chat, r.status === 204 ? (only ? '⏳ Пишу замену. Пришлю новый черновик через 1–3 минуты.' : '⏳ Запустил подготовку постов. Готовлю черновики, это 1–3 минуты. Когда закончу, напишу «✅ Готово».') : `Не получилось запустить (код ${r.status}). Запустите вручную: GitHub → Actions → «Черновики постов» → Run workflow.`, BACK);
}

async function menuAction(chat, act) {
  if (act === 'menu') return send(chat, '📋 Главное меню', MENU);
  if (act === 'help') return send(chat, HELP, BACK);
  if (act === 'src') return showSources(chat);
  if (act === 'gen') return generate(chat);
  const { data } = await readJson('channel/drafts.json', {}, 'state');
  if (act === 'drafts') return showDrafts(chat, data);
  if (act === 'stats') return send(chat, statsText(data, 30, 'Статистика за 30 дней', await subsCount()), BACK);
  if (act === 'week') return send(chat, statsText(data, 7, 'Отчёт за 7 дней', await subsCount()), BACK);
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') {
    if (!keyOk(req) || req.query.setup !== '1') return res.status(403).send('no');
    const url = `https://${req.headers.host}/api/tgbot`;
    const out = {};
    out.webhook = await tg('setWebhook', { url, secret_token: process.env.CP_WEBHOOK_SECRET || '', allowed_updates: ['message', 'callback_query'] });
    out.commands = await tg('setMyCommands', { commands: [
      { command: 'menu', description: 'Главное меню' }, { command: 'drafts', description: 'Черновики на одобрение' }, { command: 'stats', description: 'Статистика за 30 дней' },
      { command: 'week', description: 'Отчёт за неделю' }, { command: 'gen', description: 'Запросить посты сейчас' }, { command: 'sources', description: 'Источники тем' }, { command: 'help', description: 'Справка' }] });
    out.menu = await tg('setChatMenuButton', { menu_button: { type: 'commands' } });
    out.about = await tg('setMyShortDescription', { short_description: 'Редактор канала @trading_pride: черновики, статистика, отчёты.' });
    out.desc = await tg('setMyDescription', { description: 'Помогаю вести канал @trading_pride: каждый день готовлю оригинальные посты о рынках, вы одобряете их одной кнопкой. Есть статистика и отчёты по запросу.' });
    return res.status(200).json(out);
  }
  if (req.method !== 'POST') return res.status(405).send('POST only');
  if (!process.env.CP_WEBHOOK_SECRET || req.headers['x-telegram-bot-api-secret-token'] !== process.env.CP_WEBHOOK_SECRET) return res.status(403).send('bad secret');
  const upd = req.body || {}, owner = String(process.env.CP_OWNER_ID || '').replace(/\D/g, '');   // только цифры: лишние пробелы/переводы строк в значении не мешают
  try {
    const msg = upd.message;
    if (msg) {
      if (String(msg.from && msg.from.id) !== owner) { await tg('sendMessage', { chat_id: msg.chat.id, text: 'Этот бот работает только с владельцем канала.\n\nВаш Telegram id: ' + (msg.from && msg.from.id) + '\nЕсли вы владелец, впишите это число в CP_OWNER_ID (GitHub и Vercel) и сделайте Redeploy.' }); return res.status(200).send('ok'); }
      const cmd = String(msg.text || '').split(/[\s@]/)[0].toLowerCase();
      if (msg.text && !msg.text.startsWith('/')) {
        const { data: dd, sha: ss } = await readJson('channel/drafts.json', {}, 'state');
        const wid = Object.keys(dd || {}).find((k) => dd[k].await_reason);
        if (wid) {
          const w = dd[wid]; w.reason = msg.text.slice(0, 300); delete w.await_reason;
          await writeJson('channel/drafts.json', dd, ss, 'channel: причина ' + wid, 'state', true).catch(() => {});
          await tg('sendMessage', { chat_id: msg.chat.id, text: '✍️ Причину записал, учту в следующих постах.', reply_markup: { inline_keyboard: [[{ text: '🔄 Прислать замену', callback_data: 'rp:' + wid }], [{ text: '⬅️ В меню', callback_data: 'm:menu' }]] } });
          return res.status(200).send('ok');
        }
      }
      const map = { '/start': 'start', '/menu': 'menu', '/help': 'help', '/drafts': 'drafts', '/stats': 'stats', '/week': 'week', '/gen': 'gen', '/sources': 'src' };
      if (cmd === '/start') await send(msg.chat.id, 'Здравствуйте!\n\n' + HELP, MENU);
      else if (map[cmd]) await menuAction(msg.chat.id, map[cmd]);
      else await send(msg.chat.id, 'Выберите действие в меню или отправьте /help.', MENU);
      return res.status(200).send('ok');
    }
    const cb = upd.callback_query;
    if (!cb) return res.status(200).send('ok');
    if (String(cb.from && cb.from.id) !== owner) { await tg('answerCallbackQuery', { callback_query_id: cb.id, text: 'Нет доступа' }); return res.status(200).send('ok'); }
    const [act, id, arg] = String(cb.data || '').split(':');
    if (act === 'm') { const T = { gen: '⏳ Запускаю…', drafts: '📝 Загружаю…', stats: '📊 Считаю…', week: '🗓 Считаю…', src: '📚 Открываю…' }; await tg('answerCallbackQuery', { callback_query_id: cb.id, text: T[id] || '' }); await menuAction(cb.message.chat.id, id); return res.status(200).send('ok'); }
    const { data, sha } = await readJson('channel/drafts.json', {}, 'state');
    const d = data && data[id];
    const BTN = [[{ text: '✅ Опубликовать', callback_data: 'ap:' + id }, { text: '❌ Отклонить', callback_data: 'rj:' + id }]];
    const mk = (rows) => tg('editMessageReplyMarkup', { chat_id: cb.message.chat.id, message_id: cb.message.message_id, reply_markup: { inline_keyboard: rows } });
    const edit = (t, extra) => mk([[{ text: t, callback_data: 'x:' + id }], ...(extra ? [extra] : [])]);
    const toast = (text, alert) => tg('answerCallbackQuery', { callback_query_id: cb.id, text, show_alert: !!alert });
    if (act === 'x') { await toast('Это статус, нажимать не нужно'); return res.status(200).send('ok'); }
    if (!d) { await toast('Черновик не найден'); return res.status(200).send('ok'); }
    if (act === 'rr' && d.status === 'rejected') {
      if (arg === 'custom') {
        Object.keys(data).forEach((k) => { delete data[k].await_reason; }); d.await_reason = true;
        await writeJson('channel/drafts.json', data, sha, 'channel: ' + id + ' ждёт причину', 'state', true).catch(() => {});
        await toast('✍️ Напиши причину следующим сообщением');
        await tg('sendMessage', { chat_id: cb.message.chat.id, text: '✍️ Напиши причину одним сообщением. Я запомню и учту в следующих постах.' });
        return res.status(200).send('ok');
      }
      d.reason = arg === 'none' ? '' : REASONS[arg] || arg; d.reason_code = arg;
      await edit('❌ Отклонено' + (d.reason ? ' · ' + d.reason : ''), [{ text: '🔄 Прислать замену', callback_data: 'rp:' + id }, { text: '↩️ Вернуть', callback_data: 'un:' + id }]);
      await writeJson('channel/drafts.json', data, sha, 'channel: ' + id + ' причина', 'state', true).catch(() => {});
      await toast(d.reason ? 'Причина записана' : 'Отклонено без причины'); return res.status(200).send('ok');
    }
    if (act === 'rp') {
      if (d.replaced) { await toast('Замену уже заказывали'); return res.status(200).send('ok'); }
      d.replaced = true; await writeJson('channel/drafts.json', data, sha, 'channel: ' + id + ' замена', 'state', true).catch(() => {});
      await edit('⏳ Пишу замену…'); await toast('⏳ Пишу замену…'); await generate(cb.message.chat.id, d.cat); return res.status(200).send('ok');
    }
    if (act === 'un') {
      if (d.status !== 'rejected') { await toast('Вернуть можно только отклонённый'); return res.status(200).send('ok'); }
      d.status = 'pending'; delete d.reason; delete d.await_reason; await mk(BTN);
      await writeJson('channel/drafts.json', data, sha, 'channel: ' + id + ' pending', 'state', true).catch(() => {});
      await toast('↩️ Вернул в ожидание'); return res.status(200).send('ok');
    }
    if (d.status !== 'pending' && !(d.status === 'scheduled' && (act === 'pn' || act === 'us'))) { await toast('Уже обработан: ' + (ST[d.status] || d.status)); return res.status(200).send('ok'); }
    if (act === 'us') {
      d.status = 'pending'; delete d.at; await mk(BTN);
      await writeJson('channel/drafts.json', data, sha, 'channel: ' + id + ' снят с очереди', 'state', true).catch(() => {});
      await toast('↩️ Снял с очереди'); return res.status(200).send('ok');
    }
    if (act === 'ap') {
      const at = nextSlot(data, d.cat);
      d.status = 'scheduled'; d.at = at; d.owner_chat = cb.message.chat.id; d.owner_mid = cb.message.message_id;
      await edit('🕒 Выйдет ' + slotLabel(at), [{ text: '▶️ Сейчас', callback_data: 'pn:' + id }, { text: '↩️ Снять', callback_data: 'us:' + id }]);
      await writeJson('channel/drafts.json', data, sha, 'channel: ' + id + ' запланирован', 'state', true).catch(() => {});
      await toast('🕒 Запланировал: ' + slotLabel(at)); return res.status(200).send('ok');
    }
    if (act === 'pn') {
      await toast('⏳ Публикую…'); await edit('⏳ Публикую…');
      const cap = htmlText(d.text);
      const r = d.photo ? await tg((MK[d.kind] || MK.photo)[0], { chat_id: CHANNEL(), [(MK[d.kind] || MK.photo)[1]]: d.photo, caption: cap.slice(0, 1024), parse_mode: 'HTML' }) : await tg('sendMessage', { chat_id: CHANNEL(), text: cap, parse_mode: 'HTML' });
      if (!r.ok) { await mk(BTN); await toast('⚠️ Не опубликовано: ' + String(r.description || '').slice(0, 150), true); return res.status(200).send('ok'); }
      delete d.at; d.status = 'published'; d.pub = new Date().toISOString(); d.msg_id = r.result && r.result.message_id;
      const ch = CHANNEL().replace(/^@/, ''), link = /^\w+$/.test(ch) && d.msg_id ? [{ text: '🔗 Открыть в канале', url: `https://t.me/${ch}/${d.msg_id}` }] : null;
      await edit('✅ Опубликовано ' + new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' }), link);
    } else if (act === 'rj') {
      d.status = 'rejected'; d.rej = new Date().toISOString();
      await mk([[{ text: '❌ Отклонено. Почему?', callback_data: 'x:' + id }], ...Object.entries(REASONS).reduce((a, [k, v], i) => { (i % 2 ? a[a.length - 1] : a[a.push([]) - 1]).push({ text: v, callback_data: 'rr:' + id + ':' + k }); return a; }, []), [{ text: '✍️ Своя причина', callback_data: 'rr:' + id + ':custom' }, { text: '↩️ Вернуть', callback_data: 'un:' + id }]]);
    } else return res.status(200).send('ok');
    await writeJson('channel/drafts.json', data, sha, 'channel: ' + id + ' ' + d.status, 'state', true).catch(() => {});
    await toast(d.status === 'published' ? '✅ Опубликовано в канал' : '❌ Отклонено');
  } catch (e) { console.error('tgbot', e); }
  res.status(200).send('ok');
}
