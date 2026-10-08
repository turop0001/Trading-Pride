// Манифест для установки Пульта на экран «Домой» (iPhone: без этого push не работает). Нужен ключ ?k=.
import { keyOk } from '../../lib/auth';
export default function handler(req, res) {
  if (!keyOk(req)) return res.status(404).end();
  const k = encodeURIComponent(String(req.query.k || ''));
  res.setHeader('Content-Type', 'application/manifest+json');
  res.setHeader('Cache-Control', 'no-store');
  res.status(200).send(JSON.stringify({ name: 'Пульт входа', short_name: 'Пульт', start_url: `/p/${k}`, scope: '/', display: 'standalone', background_color: '#faf9f5', theme_color: '#faf9f5',
    icons: [{ src: '/icon-192.png', sizes: '192x192', type: 'image/png' }, { src: '/icon-512.png', sizes: '512x512', type: 'image/png' }] }));
}
