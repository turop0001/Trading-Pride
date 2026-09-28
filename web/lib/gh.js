// Чтение и запись JSON-файлов в GitHub-репозитории через Contents API (токен GH_TOKEN из Vercel).
const repo = () => process.env.GH_REPO || 'turop0001/Trading-Pride';
const hdr = () => ({
  Authorization: `Bearer ${process.env.GH_TOKEN}`,
  Accept: 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
});

export async function readJson(path, fallback) {
  if (!process.env.GH_TOKEN) throw new Error('GH_TOKEN не задан в переменных окружения Vercel');
  const r = await fetch(`https://api.github.com/repos/${repo()}/contents/${path}`, { headers: hdr(), cache: 'no-store' });
  if (r.status === 404) return { data: fallback, sha: null };
  if (!r.ok) throw new Error(`GitHub API ${r.status}`);
  const j = await r.json();
  return { data: JSON.parse(Buffer.from(j.content, j.encoding || 'base64').toString('utf-8')), sha: j.sha };
}

export async function writeJson(path, data, sha, message) {
  const body = {
    message,
    content: Buffer.from(JSON.stringify(data, null, 2), 'utf-8').toString('base64'),
    ...(sha ? { sha } : {}),
  };
  const r = await fetch(`https://api.github.com/repos/${repo()}/contents/${path}`, {
    method: 'PUT', headers: { ...hdr(), 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok) { const e = new Error(`GitHub API ${r.status}`); e.status = r.status; throw e; }
  return r.json();
}
