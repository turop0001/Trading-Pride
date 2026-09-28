// Доступ к личному пульту и к записи журнала/истории: ключ PULT_KEY из переменных окружения Vercel.
export function keyOk(req) {
  const k = process.env.PULT_KEY;
  if (!k) return false;
  return (req.headers['x-pult-key'] || req.query.k || '') === k;
}
