// Отдаёт страницы: '/' — страница для подписчиков (только отчёт дня), '/p/<PULT_KEY>' — личный пульт.
import html from '../../lib/html';
import { keyOk } from '../../lib/auth';
export default function handler(req, res) {
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Robots-Tag', 'noindex');
  if (req.query.p === 'pult') {
    if (!keyOk(req)) { res.status(404).send(html.friend); return; }
    res.status(200).send(html.pult);
    return;
  }
  res.status(200).send(html.friend);
}
