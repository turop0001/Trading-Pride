// Приём свечей из MT5 (советник mt5/PultBridge.mq5) — цены брокера вместо Yahoo.
// POST, заголовок x-pult-key = PULT_KEY. Тело — текст:
//   FEED1
//   SYM|TF|t,o,h,l,c;t,o,h,l,c;...      (TF: M5 | H1 | D1, t — UTC epoch открытия бара)
// Хранится в ветке `feed` (не main — чтобы не пересобирать сайт), два файла одного формата
//   { upd: epoch, syms: { XAUUSD: { M5: [[t,o,h,l,c],...], H1: [...], D1: [...] } } }:
//   feed/hist.json — полная история (советник шлёт раз в час), feed/live.json — последние бары
//   (раз в минуту, маленький — чтобы репозиторий не раздувался). Читатель склеивает оба.
import { keyOk } from '../../lib/auth';
import { readBig, writeJson, ensureBranch } from '../../lib/gh';

export const config = { api: { bodyParser: { sizeLimit: '4mb' } } };
const KEEP = { M5: 12 * 24 * 12, H1: 24 * 40, D1: 60 }; // ~12 дней M5, 40 дней H1, 60 D1
const SYMS = ['XAUUSD', 'EURUSD', 'GBPUSD', 'US500', 'NAS100', 'US30', 'GER40'];
const BR = 'feed', HIST = 'feed/hist.json', LIVE = 'feed/live.json';
const KEEP_LIVE = { M5: 120, H1: 6, D1: 3 };

function parse(txt) {
  const lines = String(txt || '').split('\n').map((s) => s.trim()).filter(Boolean);
  if (lines[0] !== 'FEED1') throw new Error('bad header');
  const out = {};
  for (const ln of lines.slice(1)) {
    const [sym, tf, body] = ln.split('|');
    if (!SYMS.includes(sym) || !KEEP[tf] || !body) continue;
    const bars = body.split(';').map((b) => b.split(',').map(Number)).filter((b) => b.length === 5 && b.every(isFinite) && b[0] > 1.5e9);
    ((out[sym] = out[sym] || {})[tf] = bars);
  }
  return out;
}


// Сторожок цикла (07.10.2026): GitHub-расписание бывает пропущено целиком, а MT5 шлёт свечи раз в минуту и от Claude не зависит.
// В окнах A (09:50–14:00) и C (16:20–18:30 Рига) по будням: если минутный цикл loop.yml не идёт (ни in_progress, ни queued) — запускаем его.
async function watchdog() {
  const t = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Riga', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date());
  const g = (k) => (t.find((x) => x.type === k) || {}).value;
  if (['Sat', 'Sun'].includes(g('weekday'))) return 'off';
  const m = (+g('hour') % 24) * 60 + +g('minute');
  if (!((m >= 590 && m <= 840) || (m >= 980 && m <= 1110))) return 'off';
  const repo = process.env.GH_REPO || 'turop0001/Trading-Pride';
  const h = { Authorization: `Bearer ${process.env.GH_TOKEN}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };
  for (const st of ['in_progress', 'queued']) {
    const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/loop.yml/runs?status=${st}&per_page=3`, { headers: h, cache: 'no-store' });
    if (!r.ok) return 'api' + r.status;
    if (((await r.json()).workflow_runs || []).length) return 'running';
  }
  const d = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/loop.yml/dispatches`, { method: 'POST', headers: { ...h, 'Content-Type': 'application/json' }, body: JSON.stringify({ ref: 'main' }) });
  return d.status === 204 ? 'dispatched' : 'dispatch' + d.status;
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') {
    const { data } = await readBig(LIVE, null, BR).catch(() => ({ data: null }));
    const s = {};
    if (data) Object.keys(data.syms || {}).forEach((k) => { const m = data.syms[k].M5 || []; s[k] = m.length ? m[m.length - 1][0] : null; });
    return res.status(200).json({ upd: data && data.upd, lastM5: s });
  }
  if (req.method !== 'POST') return res.status(405).send('POST only');
  if (!keyOk(req)) return res.status(403).send('bad key');
  let inc;
  try { inc = parse(typeof req.body === 'string' ? req.body : JSON.stringify(req.body)); } catch (e) { return res.status(400).send('ERR ' + e.message); }
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const full = Object.values(inc).some((o) => (o.M5 || []).length > 200);
      const PATH = full ? HIST : LIVE, keep = full ? KEEP : KEEP_LIVE;
      let cur = await readBig(PATH, { syms: {} }, BR);
      if (cur.missingRef) await ensureBranch(BR);
      const data = cur.data && cur.data.syms ? cur.data : { syms: {} };
      Object.keys(inc).forEach((sym) => {
        const o = (data.syms[sym] = data.syms[sym] || {});
        Object.keys(inc[sym]).forEach((tf) => {
          const m = new Map((o[tf] || []).map((b) => [b[0], b]));
          inc[sym][tf].forEach((b) => m.set(b[0], b));
          o[tf] = [...m.values()].sort((a, b) => a[0] - b[0]).slice(-keep[tf]);
        });
      });
      data.upd = Math.floor(Date.now() / 1000);
      await writeJson(PATH, data, cur.sha, full ? 'feed: история MT5' : 'feed: свечи MT5', BR, true);
      let wd = '';
      if (!full) { try { wd = await Promise.race([watchdog(), new Promise((r) => setTimeout(() => r('timeout'), 4000))]); } catch (e) { wd = 'err'; } }
      return res.status(200).send('OK ' + Object.keys(inc).join(',') + (wd && wd !== 'off' ? ' wd:' + wd : ''));
    } catch (e) {
      if (e.status !== 409 && e.status !== 422) return res.status(500).send('ERR ' + String(e.message || e));
    }
  }
  res.status(409).send('ERR conflict');
}
