// Подписки браузеров/телефонов на push-уведомления Пульта (08.10.2026).
// POST ?k=<PULT_KEY> {endpoint, keys:{p256dh,auth}} — сохранить подписку; DELETE — убрать. Хранится в ветке feed (feed/push.json),
// её читает pult_tick.py и шлёт уведомления (webpush_send.py). Только личный пульт (нужен ключ).
import { keyOk } from '../../lib/auth';
import { readJson, writeJson, ensureBranch } from '../../lib/gh';
const PATH = 'feed/push.json', BR = 'feed';
export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (!keyOk(req)) return res.status(403).json({ error: 'bad key' });
  if (req.method !== 'POST' && req.method !== 'DELETE') return res.status(405).json({ error: 'POST/DELETE' });
  const sub = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
  if (!sub.endpoint || !/^https:\/\//.test(sub.endpoint)) return res.status(400).json({ error: 'bad subscription' });
  for (let i = 0; i < 3; i++) {
    try {
      let cur = await readJson(PATH, { subs: [] }, BR).catch(async (e) => { await ensureBranch(BR); return { data: { subs: [] }, sha: null }; });
      const subs = ((cur.data && cur.data.subs) || []).filter((s) => s.endpoint !== sub.endpoint);
      if (req.method === 'POST') subs.push({ endpoint: sub.endpoint, keys: sub.keys, ua: String(req.headers['user-agent'] || '').slice(0, 80), t: Math.floor(Date.now() / 1000) });
      await writeJson(PATH, { subs: subs.slice(-20) }, cur.sha, 'push: подписка', BR, true);
      return res.status(200).json({ ok: true, n: subs.length });
    } catch (e) {
      if (e.status !== 409 && e.status !== 422) return res.status(500).json({ error: String(e.message || e) });
    }
  }
  res.status(409).json({ error: 'conflict' });
}
