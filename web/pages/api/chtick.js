// Ручной/внешний запуск будильника канала: /api/chtick?k=<ключ Пульта> (можно вызывать с cron-job.org или с любой кнопки).
import { keyOk } from '../../lib/auth';
import { channelTick } from '../../lib/chtick';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (!keyOk(req)) return res.status(403).send('bad key');
  try { return res.status(200).json(await channelTick()); } catch (e) { return res.status(500).send('ERR ' + String(e.message || e)); }
}
