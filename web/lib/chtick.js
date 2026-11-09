// Будильник канала @trading_pride независимо от расписания GitHub (09.11.2026).
// GitHub-cron опаздывал на 4–8 часов (черновики приходили в 14:00 МСК, посты выходили не в 10:00/19:00).
// Эту функцию дёргает /api/feed (MT5 шлёт свечи каждую минуту) и /api/chtick; всё идемпотентно, расписание GitHub остаётся запасным.
//  1) публикует одобренные посты (status=scheduled), чьё время `at` наступило; перед отправкой «занимает» пост (status=publishing с sha) — двойной публикации нет;
//  2) если сегодня (UTC, после 05:30) черновиков ещё нет — запускает channel_posts.yml.
import { readJson, writeJson } from './gh';

const CP = () => process.env.CP_BOT_TOKEN || '';
const CHANNEL = () => process.env.CP_CHANNEL || '@trading_pride';
const tg = (m, body) => fetch(`https://api.telegram.org/bot${CP()}/${m}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then((r) => r.json());
const MK = { photo: ['sendPhoto', 'photo'], video: ['sendVideo', 'video'], animation: ['sendAnimation', 'animation'] };
const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const htmlText = (t) => { const i = t.indexOf('\n'); return i < 0 ? '<b>' + esc(t) + '</b>' : '<b>' + esc(t.slice(0, i)) + '</b>' + esc(t.slice(i)); };
const DR = 'channel/drafts.json', BR = 'channel';
const ghh = () => ({ Authorization: `Bearer ${process.env.GH_TOKEN}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' });
const repo = () => process.env.GH_REPO || 'turop0001/Trading-Pride';

async function publishDue(data, sha, now) {
  let done = 0;
  for (const id of Object.keys(data).sort()) {
    const d = data[id];
    if (d.status === 'publishing' && !d.pub && d.claim && now - new Date(d.claim) > 5 * 60e3) d.status = 'scheduled';   // зависший захват (сбой между захватом и отправкой)
    if (d.status !== 'scheduled' || !d.at || new Date(d.at) > now) continue;
    d.status = 'publishing'; d.claim = now.toISOString();
    let w;
    try { w = await writeJson(DR, data, sha, 'channel: ' + id + ' публикуется', BR, true); } catch (e) { return { done, stop: 'conflict' }; }
    sha = w.content.sha;
    const cap = htmlText(d.text);
    const m = d.photo ? MK[d.kind] || MK.photo : null;
    let r;
    try { r = m ? await tg(m[0], { chat_id: CHANNEL(), [m[1]]: d.photo, caption: cap.slice(0, 1024), parse_mode: 'HTML' }) : await tg('sendMessage', { chat_id: CHANNEL(), text: cap, parse_mode: 'HTML' }); } catch (e) { r = { ok: false, description: String(e.message || e) }; }
    if (!r.ok) {
      d.status = 'scheduled'; d.err = String(r.description || '').slice(0, 120);
      try { w = await writeJson(DR, data, sha, 'channel: ' + id + ' не опубликован', BR, true); sha = w.content.sha; } catch (e) {}
      continue;
    }
    d.status = 'published'; d.pub = now.toISOString(); d.msg_id = r.result && r.result.message_id; delete d.at; delete d.err; delete d.claim;
    for (let k = 0; k < 3; k++) {
      try { w = await writeJson(DR, data, sha, 'channel: ' + id + ' опубликован', BR, true); sha = w.content.sha; break; }
      catch (e) { const f = await readJson(DR, {}, BR); Object.assign(data, f.data, { [id]: d }); sha = f.sha; }
    }
    done++;
    try {
      if (d.owner_chat && d.owner_mid) {
        const ch = CHANNEL().replace(/^@/, '');
        const hm = new Date(now.getTime() + 3 * 3600e3).toISOString().slice(11, 16);
        await tg('editMessageReplyMarkup', { chat_id: d.owner_chat, message_id: d.owner_mid, reply_markup: { inline_keyboard: [[{ text: '✅ Опубликовано ' + hm, callback_data: 'x:' + id }], [{ text: '🔗 Открыть в канале', url: `https://t.me/${ch}/${d.msg_id}` }]] } });
      }
    } catch (e) {}
  }
  return { done };
}

async function ensureDrafts(data, now) {
  const h = now.getUTCHours() + now.getUTCMinutes() / 60;
  if (h < 5.5 || h >= 15) return 'off';
  const today = now.toISOString().slice(0, 10);
  if (Object.values(data).some((x) => !x.urgent && String(x.ts || '').slice(0, 10) === today)) return 'have';
  const since = new Date(now.getTime() - 40 * 60e3).toISOString();
  const r = await fetch(`https://api.github.com/repos/${repo()}/actions/workflows/channel_posts.yml/runs?created=%3E%3D${since}&per_page=3`, { headers: ghh(), cache: 'no-store' });
  if (!r.ok) return 'api' + r.status;
  if (((await r.json()).workflow_runs || []).length) return 'running';
  const d = await fetch(`https://api.github.com/repos/${repo()}/actions/workflows/channel_posts.yml/dispatches`, { method: 'POST', headers: { ...ghh(), 'Content-Type': 'application/json' }, body: JSON.stringify({ ref: 'main', inputs: { dry: '0' } }) });
  return d.status === 204 ? 'dispatched' : 'dispatch' + d.status;
}

export async function channelTick() {
  if (!CP() || !process.env.GH_TOKEN) return { off: 'no env' };
  const now = new Date();
  const { data, sha } = await readJson(DR, {}, BR);
  const pub = await publishDue(data, sha, now);
  let gen = 'skip';
  try { gen = await ensureDrafts(data, now); } catch (e) { gen = 'err'; }
  return { pub: pub.done, stop: pub.stop, gen };
}
