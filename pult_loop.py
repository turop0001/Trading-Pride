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
    sh = lambda *a: subprocess.run(list(a), capture_output=True, text=True)
    sh('git', 'add', 'state')
    if sh('git', 'diff', '--cached', '--quiet').returncode == 0:
        return
    sh('git', 'commit', '-m', 'tick ' + dt.datetime.utcnow().strftime('%H:%M UTC'))
    for _ in range(3):
        sh('git', 'pull', '--rebase', '-X', 'theirs', 'origin', 'main')
        if sh('git', 'push').returncode == 0:
            return
        time.sleep(5)


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
        pult_tick.main()
        git_push()
    except Exception as e:
        print('tick error:', e)
    time.sleep(60 - dt.datetime.utcnow().second)
