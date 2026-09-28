import Head from 'next/head';
import usePultState from '../lib/usePultState';
import { WINDOW_SYMBOLS, WINDOW_LABEL, STATUS_EMOJI } from '../lib/pult';

// Упрощённая страница для друга: только статус/направление по инструменту и итог дня —
// без цен, боксов, тренда и прочих технических деталей чек-листа.
function SimpleCard({ sym, r }) {
  const emo = STATUS_EMOJI[r.line_status] || '⚪';
  return (
    <div className="card">
      <div className="card-head">
        <span>{emo}</span>
        <strong>{sym}</strong>
        <span className="dir">{r.direction || '—'}</span>
      </div>
      <div className="card-status">{r.note || r.tg_note || '—'}</div>
    </div>
  );
}

function TickLine({ state }) {
  const log = (state && state._log) || [];
  const last = log[log.length - 1];
  if (!last) return null;
  const txt = String(last.text || '').replace(/bias\s*/gi, '');
  return (
    <p className="tick">
      🕒 проверено в {last.time} Рига (окно {last.window}) — {txt}
    </p>
  );
}

function DailySummary({ ds }) {
  if (!ds) return null;
  const sign = ds.total_pct > 0 ? '+' : ds.total_pct < 0 ? '-' : '';
  return (
    <section>
      <h2>Отчёт дня · {ds.date}</h2>
      <div className="daily">
        {ds.sections.map(([w, lines]) => (
          <div key={w} style={{ marginBottom: 10 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Тип {w}:</div>
            {lines.map((l, i) => (
              <div className="daily-line" key={i}>{l}</div>
            ))}
          </div>
        ))}
        <div className="daily-total">
          🎯 Итог дня: {sign}{Math.abs(ds.total_pct).toFixed(1)}% депозита
        </div>
      </div>
    </section>
  );
}

export default function Friend() {
  const { state, error } = usePultState();

  return (
    <div className="wrap">
      <Head>
        <title>Пульт входа</title>
      </Head>
      <h1>Пульт входа</h1>
      <p className="subtitle">Статусы обновляются автоматически.</p>

      {error && <p className="err">Ошибка загрузки: {error}</p>}
      {!state && !error && <p>Загрузка…</p>}

      {state && (
        <>
          <TickLine state={state} />
          {['A', 'C'].map((w) => (
            <section key={w}>
              <h2>{WINDOW_LABEL[w]}</h2>
              <div className="cards">
                {WINDOW_SYMBOLS[w].map((sym) => (
                  <SimpleCard key={sym} sym={sym} r={state[`${sym}_${w}`] || {}} />
                ))}
              </div>
            </section>
          ))}
          <DailySummary ds={state._daily_summary} />
        </>
      )}
    </div>
  );
}
