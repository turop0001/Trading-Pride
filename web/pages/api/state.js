// Серверный роут: читает state/pult_state.json из приватного GitHub-репозитория через
// Contents API (нужен GH_TOKEN с правом чтения репозитория, задаётся в Vercel → Settings →
// Environment Variables). Кэш на 20 сек на уровне CDN, чтобы не долбить GitHub API на каждый
// клиентский опрос — тик всё равно обновляет state не чаще чем раз в ~5 мин.
export default async function handler(req, res) {
  const token = process.env.GH_TOKEN;
  const repo = process.env.GH_REPO || 'turop0001/Trading-Pride';

  if (!token) {
    res.status(500).json({ error: 'GH_TOKEN не задан в переменных окружения Vercel' });
    return;
  }

  try {
    const r = await fetch(`https://api.github.com/repos/${repo}/contents/state/pult_state.json?ref=state`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
      },
      cache: 'no-store',
    });

    if (!r.ok) {
      const body = await r.text();
      res.status(r.status).json({ error: `GitHub API ${r.status}`, body });
      return;
    }

    const data = await r.json();
    const text = Buffer.from(data.content, data.encoding || 'base64').toString('utf-8');
    const state = JSON.parse(text);

    res.setHeader('Cache-Control', 's-maxage=8, stale-while-revalidate=20');
    res.status(200).json(state);
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
}
