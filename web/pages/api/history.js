// Архив сигналов: state/history.json. Туда попадают карточки со статусом «Вход» (пишет робот
// в GitHub Actions) и карточки, где трейдер отметил «Вошёл» / «Закрыл» (пишет эта страница).
import { readJson, writeJson } from '../../lib/gh';
import { keyOk } from '../../lib/auth';
const PATH = 'state/history.json';
const KEYS = ['id', 'date', 'symbol', 'type', 'side', 'entry', 'stop', 'target', 'risk', 'result', 'narr', 'mine'];

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (!keyOk(req)) { res.status(401).json({ error: 'нет доступа (PULT_KEY)' }); return; }
  try {
    if (req.method === 'GET') {
      const { data } = await readJson(PATH, []);
      res.status(200).json({ items: Array.isArray(data) ? data : [] });
      return;
    }
    const { op, item } = req.body || {};
    if (op !== 'upsert' || !item || !item.id) { res.status(400).json({ error: 'bad op' }); return; }
    for (let a = 0; a < 3; a++) {
      const { data, sha } = await readJson(PATH, []);
      const items = Array.isArray(data) ? data : [];
      const clean = {};
      KEYS.forEach((k) => { if (item[k] !== undefined && item[k] !== null) clean[k] = item[k]; });
      const i = items.findIndex((x) => x.id === clean.id);
      if (i >= 0) items[i] = { ...items[i], ...clean }; else items.push(clean);
      try {
        await writeJson(PATH, items, sha, `history: ${clean.id} ${clean.mine || ''}`);
        res.status(200).json({ ok: true, items });
        return;
      } catch (e) {
        if (e.status === 409 || e.status === 422) continue;
        res.status(200).json({ ok: false, error: String(e.message) });
        return;
      }
    }
    res.status(200).json({ ok: false, error: 'конфликт записи' });
  } catch (e) {
    res.status(200).json({ items: [], error: String(e.message || e) });
  }
}
