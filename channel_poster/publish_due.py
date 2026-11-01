#!/usr/bin/env python3
"""Публикует в канал одобренные посты, чьё время (слот 10:00 / 19:00 МСК) наступило. Запускается по расписанию GitHub Actions."""
import os, json, datetime as dt, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run

CHANNEL = os.environ.get('CP_CHANNEL') or '@trading_pride'
MK = {'photo': ('sendPhoto', 'photo'), 'video': ('sendVideo', 'video'), 'animation': ('sendAnimation', 'animation')}


def main():
    drafts, sha = run.load_drafts()
    now = dt.datetime.now(dt.timezone.utc); done = 0
    for did, d in sorted(drafts.items()):
        if d.get('status') != 'scheduled' or not d.get('at'): continue
        if dt.datetime.fromisoformat(d['at'].replace('Z', '+00:00')) > now: continue
        cap = run.html_text(d['text'])
        if d.get('photo'):
            m, f = MK.get(d.get('kind'), MK['photo'])
            r = run.tg(m, {'chat_id': CHANNEL, f: d['photo'], 'caption': cap[:1024], 'parse_mode': 'HTML'})
        else:
            r = run.tg('sendMessage', {'chat_id': CHANNEL, 'text': cap, 'parse_mode': 'HTML'})
        if not r.get('ok'):
            print('! не опубликовано', did, r); continue
        d['status'] = 'published'; d['pub'] = now.isoformat(timespec='seconds'); d['msg_id'] = r['result']['message_id']; d.pop('at', None); done += 1
        print('опубликован', did)
        ch = CHANNEL.lstrip('@')
        try:
            if d.get('owner_chat') and d.get('owner_mid'):
                kb = [[{'text': '✅ Опубликовано ' + (now + dt.timedelta(hours=3)).strftime('%H:%M'), 'callback_data': 'x:' + did}], [{'text': '🔗 Открыть в канале', 'url': 'https://t.me/%s/%s' % (ch, d['msg_id'])}]]
                run.tg('editMessageReplyMarkup', {'chat_id': d['owner_chat'], 'message_id': d['owner_mid'], 'reply_markup': {'inline_keyboard': kb}})
        except Exception as e:
            print('кнопку не обновил:', str(e)[:80])
    if done: run.save_drafts(drafts, sha)
    print('Опубликовано:', done)


if __name__ == '__main__':
    main()
