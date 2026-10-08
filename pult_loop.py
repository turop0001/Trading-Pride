"""Минутный цикл внутри одного запуска GitHub Actions (29.09.2026).

Расписание GitHub Actions срабатывает с опозданием 5-20 минут, поэтому вместо отдельного
запуска на каждую проверку один запуск держится всё окно и делает проверку каждые 60 секунд,
сохраняя state в репозиторий после каждого изменения. Остальные 5-минутные запуски из
расписания остаются страховкой: если этот цикл упадёт, проверки продолжатся по-старому.
"""
import subprocess, time, sys, datetime as dt
import live_check as lc
import pult_tick

HB = 'state/loop_heartbeat.txt'


def git_push():
    # 02.10.2026: состояние уходит в ветку state (не в main) — см. state_sync.py
    import state_sync
    state_sync.push()


# 02.10.2026: цикл живёт часами — после пуша нового кода он продолжал работать на старом.
# Теперь каждую минуту подтягиваем main и, если поменялся код, перезагружаем модули.
def _hot_reload():
    import importlib
    sh = lambda *a: subprocess.run(list(a), capture_output=True, text=True)
    sh('git', 'fetch', '-q', 'origin', 'main')
    ch = sh('git', 'diff', '--name-only', 'HEAD', 'origin/main', '--', '*.py').stdout.split()
    if not ch:
        return
    sh('git', 'stash', '-q'); sh('git', 'pull', '-q', '--rebase', 'origin', 'main'); sh('git', 'stash', 'pop', '-q')
    bad = sh('git', 'diff', '--name-only', '--diff-filter=U').stdout.split()
    if bad:                                  # конфликт состояния при pop: берём свою (stash) версию
        for f in bad: sh('git', 'checkout', '--theirs', '--', f)
        sh('git', 'reset', '-q'); sh('git', 'stash', 'drop', '-q')
    import pult_ctx, pult_s1, pult_rules, state_sync
    for mod in (pult_ctx, pult_s1, pult_rules, state_sync, lc, pult_tick):
        try: importlib.reload(mod)
        except Exception as e: print('reload failed', mod.__name__, e)
    print('code reloaded', ch)


import state_sync
state_sync.pull()
r0, _ = lc.riga_now()
m0 = r0.hour * 60 + r0.minute
START, END = (595, 845) if m0 < 900 else (985, 1145)   # окно A или окно C (+5 мин на отчёт закрытия)
while True:
    riga, _ = lc.riga_now()
    m = riga.hour * 60 + riga.minute
    if m >= END:
        break
    if m < START:
        time.sleep(30); continue
    try:
        open(HB, 'w').write(str(int(time.time())))
        _hot_reload()
        pult_tick.main()
        git_push()
    except Exception as e:
        print('tick error:', e)
    time.sleep(20 - dt.datetime.utcnow().second % 20)   # 08.10.2026: тик каждые 20 с (раньше 60) — меньше задержка сигналов
