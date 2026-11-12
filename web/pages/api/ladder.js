// Синхронизация пульта лестницы между устройствами: feed/ladder.json (ветка feed — деплой от неё отключён).
// GET -> {rev, state}; POST {state, base} -> {ok, rev} | {conflict:true, rev, state}.
import { readJson, writeJson, ensureBranch } from '../../lib/gh';
import { keyOk } from '../../lib/auth';
const PATH = 'feed/ladder.json', BR = 'feed';
export const config = { api: { bodyParser: { sizeLimit: '2mb' } } };

async function cur() {
  try { return await readJson(PATH, null, BR); }
  catch (e) { await ensureBranch(BR); return readJson(PATH, null, BR); }
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (!keyOk(req)) { res.status(401).json({ error: 'нет доступа' }); return; }
  try {
    if (req.method === 'GET') {
      const { data } = await cur();
      res.status(200).json(data ? { rev: data.rev, state: data.state } : { rev: 0, state: null });
      return;
    }
    if (req.method !== 'POST') { res.status(405).json({ error: 'method' }); return; }
    const { state, base, force } = req.body || {};
    if (!state || typeof state !== 'object') { res.status(400).json({ error: 'bad state' }); return; }
    for (let a = 0; a < 3; a++) {
      const { data, sha } = await cur();
      const rev = data ? data.rev : 0;
      if (!force && (base || 0) !== rev && data) { res.status(200).json({ conflict: true, rev, state: data.state }); return; }
      try {
        await writeJson(PATH, { rev: rev + 1, ts: Date.now(), state }, sha, 'ladder: sync', BR, true);
        res.status(200).json({ ok: true, rev: rev + 1 });
        return;
      } catch (e) {
        if (e.status === 409 || e.status === 422) continue;
        res.status(200).json({ ok: false, error: e.status === 403 ? 'нет права записи у GH_TOKEN' : String(e.message) });
        return;
      }
    }
    res.status(200).json({ ok: false, error: 'конфликт записи' });
  } catch (e) { res.status(200).json({ ok: false, error: String(e.message || e) }); }
}
