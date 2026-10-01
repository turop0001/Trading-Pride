// Сигналы Пульта простым текстом для советника MT5 (mt5/PultBridge.mq5).
// Строка: id|символ|side|t_utc_epoch|entry|stop|tp|status (status: open | tp | sl), только за 2 дня.
import { readJson } from '../../lib/gh';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  try {
    const { data } = await readJson('state/pult_state.json', {});
    const now = Date.now();
    const lines = [];
    Object.keys(data || {}).forEach((k) => {
      const r = data[k];
      if (!/_(A|C)$/.test(k) || !r || !r.signal) return;
      const sg = r.signal;
      const t = Date.parse(String(sg.t_utc).replace(' ', 'T').replace('+00:00', 'Z'));
      if (!t || now - t > 2 * 86400000) return;
      const note = String(r.note || '');
      const status = note.indexOf('→ TP') >= 0 ? 'tp' : note.indexOf('→ SL') >= 0 ? 'sl' : (note.indexOf('→ БУ') >= 0 || note.indexOf('закрыта в 22:00') >= 0) ? 'closed' : 'open';
      const sym = r.sym || k.split('_')[0];
      lines.push([`${sg.date}_${sym}_${sg.window || k.split('_')[1]}`, sym, sg.side, Math.floor(t / 1000), sg.entry, sg.stop, sg.tp, status, sg.be_at || 0].join('|'));
    });
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.status(200).send('PULT1\n' + Math.floor(now / 1000) + '\n' + lines.join('\n') + '\n');
  } catch (e) {
    res.status(500).send('ERR ' + String(e.message || e));
  }
}
