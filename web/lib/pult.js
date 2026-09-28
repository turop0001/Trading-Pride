// Общие константы/хелперы для обеих страниц (главный дашборд и страница для друга).
// Данные приходят из /api/state, который читает state/pult_state.json из GitHub-репозитория
// (тот же файл, что коммитит GitHub Actions после каждого тика).

export const WINDOW_SYMBOLS = {
  A: ['XAUUSD', 'EURUSD', 'GBPUSD', 'US500', 'NAS100', 'US30', 'GER40'],
  C: ['XAUUSD', 'EURUSD', 'GBPUSD'],
};

export const WINDOW_LABEL = {
  A: 'Тип A · Азия → Франкфурт/Лондон (10:00–14:00 Рига)',
  C: 'Тип C · Лондон → NY (16:30–18:30 Рига)',
};

export const STATUS_EMOJI = {
  skip: '⚪',
  entry: '🟢',
  watch: '🟡',
  prep: '⚠️',
};

export const STATUS_COLOR = {
  skip: '#9aa0a6',
  entry: '#22c55e',
  watch: '#eab308',
  prep: '#f59e0b',
};

export function cardFor(state, sym, win) {
  return (state && state[`${sym}_${win}`]) || { sym, window: win };
}

export function trendText(t) {
  if (!t || !t.tr || t.tr === 'нет данных') return null;
  const pct = t.pct != null ? ` (${t.pct >= 0 ? '+' : ''}${t.pct}%)` : '';
  return `${t.tr}${pct}`;
}
