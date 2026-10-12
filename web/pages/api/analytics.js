// Аналитика сделок: последние 10 сделок Типа A и Типа C (state/analytics.json в ветке state; до первого тика — копия в main).
// GET, ключ PULT_KEY. Пишет файл робот (analytics_gen.py), сайт только читает.
import { readBig } from '../../lib/gh';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  // Чтение открыто (12.10.2026): страница друга показывает те же графики сделок, что и личный Пульт. Запись только у робота.
  try {
    let { data, missingRef } = await readBig('state/analytics.json', null, 'state');
    if (!data || missingRef) ({ data } = await readBig('state/analytics.json', { A: [], C: [] }));
    res.status(200).json({ A: (data && data.A) || [], C: (data && data.C) || [] });
  } catch (e) {
    res.status(200).json({ error: String(e.message || e), A: [], C: [] });
  }
}
