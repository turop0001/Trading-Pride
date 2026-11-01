# Автопостинг @trading_pride

Раз в день (05:00 UTC) GitHub Actions читает публичные страницы 20 трейдинг-каналов (только темы и ажиотаж), пишет 2 оригинальных
поста (будни: новость + умное/смешное/мотивация по кругу; выходные: две не-новости) и присылает их в личку с кнопками
«Опубликовать / Отклонить». Публикует в канал веб-хук `/api/tgbot` после нажатия кнопки.

## Запуск (один раз)
1. @BotFather → /newbot → токен. Добавить бота администратором канала @trading_pride (право публиковать). Написать боту /start из личного аккаунта.
2. Свой числовой id: любой бот «id» или `getUpdates` бота. Это `CP_OWNER_ID`.
3. GitHub → Settings → Secrets: `ANTHROPIC_API_KEY`, `CP_BOT_TOKEN`, `CP_OWNER_ID`.
4. Vercel → Environment Variables: `CP_BOT_TOKEN`, `CP_OWNER_ID`, `CP_CHANNEL=@trading_pride`, `CP_WEBHOOK_SECRET` (любая длинная случайная строка). Передеплой.
5. Открыть один раз `https://trading-pride-three.vercel.app/api/tgbot?setup=1&k=<ключ Пульта>` — должно вернуться `"ok":true`.
6. GitHub → Actions → «Черновики постов» → Run workflow, dry=1 — посмотреть тексты в логе; потом dry=0.
