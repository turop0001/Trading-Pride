// Журнал реальных сделок: state/journal.json в репозитории. GET — список, POST {op:'add',doc} / {op:'del',id}.
// Для записи GH_TOKEN нужен с правом Contents: Read and write; без него журнал отдаётся только на чтение.
import { readJson, writeJson } from '../../lib/gh';
import { keyOk } from '../../lib/auth';
const PATH = 'state/journal.json';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (!keyOk(req)) { res.status(401).json({ error: 'нет доступа (PULT_KEY)' }); return; }
  try {
    if (req.method === 'GET') {
      const { data } = await readJson(PATH, []);
      res.status(200).json({ items: data });
      return;
    }
    if (req.method !== 'POST') { res.status(405).json({ error: 'method' }); return; }
    const { op, doc, id } = req.body || {};
    for (let attempt = 0; attempt < 3; attempt++) {
      const { data, sha } = await readJson(PATH, []);
      let items = Array.isArray(data) ? data : [];
      let newId = null;
      if (op === 'add' && doc && typeof doc === 'object') {
        newId = 'j' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
        const clean = {};
        ['symbol', 'type', 'side', 'date', 'out', 'r', 'usd', 'note', 'why', 'ts'].forEach((k) => { if (doc[k] !== undefined) clean[k] = doc[k]; });
        items.push({ id: newId, ...clean });
      } else if (op === 'del' && id) {
        items = items.filter((x) => x.id !== id);
      } else { res.status(400).json({ error: 'bad op' }); return; }
      try {
        await writeJson(PATH, items, sha, `journal: ${op} ${newId || id}`);
        res.status(200).json({ ok: true, id: newId, items });
        return;
      } catch (e) {
        if (e.status === 409 || e.status === 422) continue; // файл изменился параллельно — повтор
        res.status(200).json({ ok: false, error: e.status === 403 ? 'нет права записи у GH_TOKEN' : String(e.message) });
        return;
      }
    }
    res.status(200).json({ ok: false, error: 'конфликт записи, повторите' });
  } catch (e) {
    res.status(200).json({ error: String(e.message || e) });
  }
}
