// Цены для калькулятора лота (еженедельно, 15.10.2026).
// Vercel Cron (vercel.json, пн 06:00 UTC) вызывает GET → берём последнюю цену закрытия M5 из feed/live.json
// (цены брокера из MT5) и сохраняем в feed/prices.json (ветка feed — сайт не пересобирается).
// Обычный GET (страница пульта) отдаёт сохранённые цены; если файла ещё нет — считает из live.json на лету.
import { readBig, writeJson, ensureBranch } from '../../lib/gh';

const BR = 'feed', LIVE = 'feed/live.json', FILE = 'feed/prices.json';
const DEC = { EURUSD: 4, GBPUSD: 4, XAUUSD: 1, US500: 0, NAS100: 0, GER40: 0, US30: 0, AUDUSD: 4, USDJPY: 2 };

async function fresh() {
  const { data } = await readBig(LIVE, null, BR);
  if (!data || !data.syms) throw new Error('feed/live.json пуст');
  const px = {};
  Object.keys(DEC).forEach((s) => {
    const m = (data.syms[s] || {}).M5 || [];
    if (m.length) px[s] = +m[m.length - 1][4].toFixed(DEC[s]);
  });
  return { upd: Math.floor(Date.now() / 1000), px };
}

const isCron = (req) => {
  const s = process.env.CRON_SECRET;
  if (s && req.headers.authorization === `Bearer ${s}`) return true;
  return !s && String(req.headers['user-agent'] || '').startsWith('vercel-cron');
};

export default async function handler(req, res) {
  try {
    if (isCron(req)) {
      const cur = await readBig(FILE, null, BR);
      if (cur.missingRef) await ensureBranch(BR);
      const d = await fresh();
      await writeJson(FILE, d, cur.sha, 'prices: еженедельное обновление цен калькулятора', BR);
      res.setHeader('Cache-Control', 'no-store');
      return res.status(200).json({ ok: true, ...d });
    }
    res.setHeader('Cache-Control', 'public, s-maxage=3600, stale-while-revalidate=86400');
    const { data } = await readBig(FILE, null, BR);
    return res.status(200).json(data && data.px ? data : await fresh());
  } catch (e) {
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json({ error: String(e.message || e), px: {} });
  }
}
