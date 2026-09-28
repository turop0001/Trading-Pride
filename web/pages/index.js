import Head from 'next/head';
import usePultState from '../lib/usePultState';
import { WINDOW_SYMBOLS, WINDOW_LABEL, STATUS_EMOJI, trendText } from '../lib/pult';

function Card({ sym, win, r }) {
  const emo = STATUS_EMOJI[r.line_status] || '⚪';
  const t1 = trendText(r.trend_h1);
  const t2 = trendText(r.trend_d1);
  return (
    <div className="card">
      <div className="card-head">
        <span>{emo}</span>
        <strong>{sym}</strong>
        <span className="dir">{r.direction || '—'}</span>
      </div>
      <div className="card-status">{r.note || r.tg_note || '—'}</div>
      {r.price != null && (
        <div className="card-row">
          Цена: {r.price}{r.checked_at ? ` в ${r.checked_at} Рига` : ''}
        </div>
      )}
      {r.boxL != null && (
        <div className="card-row">
          {win === 'C' ? 'Бокс Лондона' : 'Бокс Азии'}: {r.boxL} – {r.boxH}
        </div>
      )}
      {r.prevL != null && win !== 'C' && (
        <div className="card-row">Вчерашний бокс: {r.prevL} – {r.prevH}</div>
      )}
      {(t1 || t2) && (
        <div className="card-row">
          Тренд (усилитель, не фильтр): {[t1 && `H1(7д) ${t1}`, t2 && `D1(14д) ${t2}`].filter(Boolean).join(' · ')}
        </div>
      )}
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

export default function Home() {
  const { state, error, updatedAt } = usePultState();

  return (
    <div className="wrap">
      <Head>
        <title>Пульт входа</title>
      </Head>
      <h1>Пульт входа</h1>
      <p className="subtitle">
        Данные обновляются автоматически из GitHub Actions (раз в ~5 мин в торговое окно).
        {updatedAt && ` Страница проверяла обновление в ${updatedAt.toLocaleTimeString('ru-RU')}.`}
      </p>

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
                  <Card key={sym} sym={sym} win={w} r={state[`${sym}_${w}`] || {}} />
                ))}
              </div>
            </section>
          ))}
          <DailySummary ds={state._daily_summary} />
        </>
      )}

      <p className="foot">
        Пульт · FundingPips $25,000 · <a href="/friend">упрощённая страница для друга</a>
      </p>
    </div>
  );
}
