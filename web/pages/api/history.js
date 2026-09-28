// Архив карточек сигналов: state/history.json (если файла ещё нет — пустой список).
import { readJson } from '../../lib/gh';
export default async function handler(req, res) {
  try {
    const { data } = await readJson('state/history.json', []);
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
    res.status(200).json({ items: Array.isArray(data) ? data : [] });
  } catch (e) {
    res.status(200).json({ items: [], error: String(e.message || e) });
  }
}
