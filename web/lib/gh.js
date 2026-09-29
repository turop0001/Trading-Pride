// Чтение и запись JSON-файлов в GitHub-репозитории через Contents API (токен GH_TOKEN из Vercel).
const repo = () => process.env.GH_REPO || 'turop0001/Trading-Pride';
const hdr = () => ({
  Authorization: `Bearer ${process.env.GH_TOKEN}`,
  Accept: 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
});

export async function readJson(path, fallback, branch) {
  if (!process.env.GH_TOKEN) throw new Error('GH_TOKEN не задан в переменных окружения Vercel');
  const r = await fetch(`https://api.github.com/repos/${repo()}/contents/${path}${branch ? `?ref=${branch}` : ''}`, { headers: hdr(), cache: 'no-store' });
  if (r.status === 404) return { data: fallback, sha: null };
  if (!r.ok) throw new Error(`GitHub API ${r.status}`);
  const j = await r.json();
  return { data: JSON.parse(Buffer.from(j.content, j.encoding || 'base64').toString('utf-8')), sha: j.sha };
}

export async function writeJson(path, data, sha, message, branch, compact) {
  const body = {
    message,
    content: Buffer.from(compact ? JSON.stringify(data) : JSON.stringify(data, null, 2), 'utf-8').toString('base64'),
    ...(sha ? { sha } : {}),
    ...(branch ? { branch } : {}),
  };
  const r = await fetch(`https://api.github.com/repos/${repo()}/contents/${path}`, {
    method: 'PUT', headers: { ...hdr(), 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok) { const e = new Error(`GitHub API ${r.status}`); e.status = r.status; throw e; }
  return r.json();
}

// Большой файл (>1 МБ) Contents API отдаёт без content — читаем «сырым» + sha отдельно.
export async function readBig(path, fallback, branch) {
  const q = `https://api.github.com/repos/${repo()}/contents/${path}${branch ? `?ref=${branch}` : ''}`;
  const m = await fetch(q, { headers: { ...hdr(), Accept: 'application/vnd.github.object+json' }, cache: 'no-store' });
  if (m.status === 404) return { data: fallback, sha: null, missingRef: true };
  if (!m.ok) throw new Error(`GitHub API ${m.status}`);
  const meta = await m.json();
  const r = await fetch(q, { headers: { ...hdr(), Accept: 'application/vnd.github.raw' }, cache: 'no-store' });
  if (!r.ok) throw new Error(`GitHub API ${r.status}`);
  return { data: JSON.parse(await r.text()), sha: meta.sha };
}

export async function ensureBranch(branch) {
  const b = await fetch(`https://api.github.com/repos/${repo()}/git/ref/heads/${branch}`, { headers: hdr(), cache: 'no-store' });
  if (b.ok) return;
  const m = await fetch(`https://api.github.com/repos/${repo()}/git/ref/heads/main`, { headers: hdr(), cache: 'no-store' });
  const sha = (await m.json()).object.sha;
  await fetch(`https://api.github.com/repos/${repo()}/git/refs`, { method: 'POST', headers: { ...hdr(), 'Content-Type': 'application/json' }, body: JSON.stringify({ ref: `refs/heads/${branch}`, sha }) });
}
