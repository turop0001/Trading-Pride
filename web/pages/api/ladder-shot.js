// Распознавание скрина торгового сигнала. POST {image: dataURL|base64, syms:[...]} -> {sym,dir,entry,sl,tp,note}.
// Нужна переменная ANTHROPIC_API_KEY в Vercel (необязательно LADDER_MODEL).
import { keyOk } from '../../lib/auth';
export const config = { api: { bodyParser: { sizeLimit: '4mb' } }, maxDuration: 60 };

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (!keyOk(req)) { res.status(401).json({ error: 'нет доступа' }); return; }
  if (req.method !== 'POST') { res.status(405).json({ error: 'method' }); return; }
  if (!process.env.ANTHROPIC_API_KEY) { res.status(200).json({ error: 'nokey' }); return; }
  try {
    let { image, syms } = req.body || {};
    if (!image) { res.status(400).json({ error: 'нет изображения' }); return; }
    let mt = 'image/jpeg';
    const m = /^data:(image\/[a-z+]+);base64,(.*)$/s.exec(image);
    if (m) { mt = m[1]; image = m[2]; }
    const list = JSON.stringify(Array.isArray(syms) ? syms : []);
    const prompt = `На изображении торговый сигнал. Извлеки параметры и верни ТОЛЬКО JSON без пояснений:
{"sym": один из ${list} (GOLD/XAU → XAUUSD, DAX/DE40 → GER40, NASDAQ/US100/USTEC → NAS100, SPX/S&P → US500, DOW/DJ30 → US30, FTSE → UK100) или null,
 "dir": "L" для buy/long или "S" для sell/short,
 "entry": число, "sl": число, "tp": число (если тейков несколько — первый),
 "note": короткая строка с прочими условиями сигнала на русском или ""}`;
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: process.env.LADDER_MODEL || 'claude-sonnet-4-5', max_tokens: 400,
        messages: [{ role: 'user', content: [{ type: 'image', source: { type: 'base64', media_type: mt, data: image } }, { type: 'text', text: prompt }] }],
      }),
    });
    const j = await r.json();
    if (!r.ok) { res.status(200).json({ error: (j.error && j.error.message) || ('API ' + r.status) }); return; }
    const txt = (j.content || []).map((c) => c.text || '').join('');
    const mm = /\{[\s\S]*\}/.exec(txt);
    if (!mm) { res.status(200).json({ error: 'пустой ответ' }); return; }
    res.status(200).json({ ok: true, r: JSON.parse(mm[0]) });
  } catch (e) { res.status(200).json({ error: String(e.message || e) }); }
}
