// Комментарии к сделкам во вкладке «Аналитика сделок»: state/ac_comments.json в main.
// GET -> {items:{<тип>_<пара>_<день>:{text,at,sym,day,typ,n}}}; POST {id,text,meta} — записать/очистить комментарий.
// Разбор комментариев по запросу даёт Claude в чате: читает этот файл.
import { readJson, writeJson } from '../../lib/gh';
import { keyOk } from '../../lib/auth';
const PATH = 'state/ac_comments.json';
const ID = /^[AC]_[A-Z0-9]{3,8}_\d{4}-\d{2}-\d{2}$/;

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (!keyOk(req)) { res.status(401).json({ error: 'нет доступа (PULT_KEY)' }); return; }
  try {
    if (req.method === 'GET') {
      const { data } = await readJson(PATH, {});
      res.status(200).json({ items: data && typeof data === 'object' ? data : {} });
      return;
    }
    if (req.method !== 'POST') { res.status(405).json({ error: 'method' }); return; }
    const { id, text, meta } = req.body || {};
    if (!id || !ID.test(String(id)) || typeof text !== 'string' || text.length > 8000) { res.status(400).json({ error: 'bad input' }); return; }
    for (let attempt = 0; attempt < 3; attempt++) {
      const { data, sha } = await readJson(PATH, {});
      const items = data && typeof data === 'object' ? data : {};
      if (text.trim() === '') delete items[id];
      else {
        const m = meta && typeof meta === 'object' ? meta : {};
        items[id] = { text, at: new Date().toISOString(), sym: String(m.sym || id.split('_')[1]), day: String(m.day || id.split('_')[2]), typ: id[0], n: Number(m.n) || null };
      }
      try {
        await writeJson(PATH, items, sha, `ac_comments: ${id}`);
        res.status(200).json({ ok: true });
        return;
      } catch (e) {
        if (e.status === 409 || e.status === 422) continue;
        res.status(200).json({ ok: false, error: e.status === 403 ? 'нет права записи у GH_TOKEN' : String(e.message) });
        return;
      }
    }
    res.status(200).json({ ok: false, error: 'конфликт записи, повторите' });
  } catch (e) {
    res.status(200).json({ ok: false, error: String(e.message || e) });
  }
}
