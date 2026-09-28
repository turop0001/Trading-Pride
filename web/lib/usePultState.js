import { useEffect, useRef, useState } from 'react';

// Опрашивает /api/state каждые POLL_MS мс. Сам тик в GitHub Actions обновляет данные не
// чаще раза в ~5 минут в торговое окно, но частый лёгкий опрос (раз в 30 сек) даёт ощущение
// "обновляется само" без необходимости обновлять страницу руками.
const POLL_MS = 30000;

export default function usePultState() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const stopped = useRef(false);

  useEffect(() => {
    stopped.current = false;
    async function load() {
      try {
        const r = await fetch('/api/state', { cache: 'no-store' });
        const d = await r.json();
        if (stopped.current) return;
        if (d && d.error) {
          setError(d.error);
        } else {
          setState(d);
          setError(null);
          setUpdatedAt(new Date());
        }
      } catch (e) {
        if (!stopped.current) setError(String(e));
      }
    }
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      stopped.current = true;
      clearInterval(id);
    };
  }, []);

  return { state, error, updatedAt };
}
