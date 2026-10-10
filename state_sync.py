"""Состояние Пульта живёт в ветке `state` (02.10.2026).

Минутные коммиты состояния шли в main и каждый раз запускали сборку на Vercel — лимит деплоев
(Hobby) упирался в потолок и блокировал выкладку сайта. Теперь состояние (pult_state.json,
pult_docs/, shots/, loop_heartbeat.txt, pult_artifact.json) пушится в отдельную ветку `state` одним
коммитом без истории (force-push) — Vercel для неё сборку отключает (vercel.json).
В main остаются только редкие записи: state/history.json, state/journal.json.

Переходный период: пока на Vercel работает старая версия сайта (читает state из main), раз в
MIRROR_SEC секунд и сразу при изменении сигналов (то, что читает советник MT5) состояние
дублируется и в main. Когда новый сайт выложен — поставить MIRROR_SEC = 0 (зеркало отключится).
"""
import os, io, json, hashlib, shutil, subprocess, tarfile, time, datetime as dt

ROOT = os.path.dirname(os.path.abspath(__file__))
ST = os.path.join(ROOT, 'state')
WT = os.path.join(ROOT, '_st')
BR = 'state'
FILES = ['pult_state.json', 'pult_artifact.json', 'loop_heartbeat.txt', 'mirror.json', 'analytics.json']
DIRS = ['pult_docs', 'shots']
MIRROR_SEC = 0     # 0 = зеркало в main выключено (с 04.10.2026: новый сайт читает ветку state)


def sh(*a, cwd=ROOT, **k):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True, **k)


def pull():
    """Подтянуть свежее состояние из ветки state в ./state (перед тиком / при старте цикла)."""
    r = sh('git', 'fetch', '-q', '--depth=1', 'origin', BR)
    if r.returncode:
        print('state: fetch failed', (r.stderr or '')[-200:]); return False
    p = subprocess.run(['git', 'archive', 'FETCH_HEAD', 'state'], cwd=ROOT, capture_output=True)
    if p.returncode or not p.stdout:
        print('state: archive failed'); return False
    tarfile.open(fileobj=io.BytesIO(p.stdout)).extractall(ROOT)
    return True


def _wt_init():
    if not os.path.isdir(os.path.join(WT, '.git')):
        os.makedirs(WT, exist_ok=True)
        sh('git', 'init', '-q', cwd=WT)
        url = sh('git', 'remote', 'get-url', 'origin').stdout.strip()
        sh('git', 'remote', 'add', 'origin', url, cwd=WT)
        hdr = sh('git', 'config', '--get-all', 'http.https://github.com/.extraheader').stdout.split('\n')
        for h in [x for x in hdr if x.strip()]:
            sh('git', 'config', '--add', 'http.https://github.com/.extraheader', h, cwd=WT)
        sh('git', 'config', 'user.name', 'pult-bot', cwd=WT)
        sh('git', 'config', 'user.email', 'pult-bot@users.noreply.github.com', cwd=WT)


def _copy_to_wt():
    base = os.path.join(WT, 'state'); os.makedirs(base, exist_ok=True)
    for f in FILES:
        s = os.path.join(ST, f)
        if os.path.exists(s): shutil.copy2(s, os.path.join(base, f))
    for d in DIRS:
        s = os.path.join(ST, d)
        if os.path.isdir(s): shutil.copytree(s, os.path.join(base, d), dirs_exist_ok=True)
    # конфиг Vercel в самой ветке: сборка state отключена (git.deploymentEnabled), как у ветки feed
    v = os.path.join(ROOT, 'web', 'vercel.json')
    if os.path.exists(v):
        os.makedirs(os.path.join(WT, 'web'), exist_ok=True); shutil.copy2(v, os.path.join(WT, 'web', 'vercel.json'))


def _push_branch():
    _wt_init(); _copy_to_wt()
    sh('git', 'add', '-A', cwd=WT)
    tree = sh('git', 'write-tree', cwd=WT).stdout.strip()
    if not tree: return False
    last = sh('git', 'rev-parse', '-q', '--verify', 'refs/remotes/origin/state^{tree}', cwd=WT).stdout.strip()
    if last == tree: return True      # ничего не изменилось
    c = sh('git', 'commit-tree', tree, '-m', 'state ' + dt.datetime.utcnow().strftime('%d.%m %H:%M UTC'), cwd=WT).stdout.strip()
    for _ in range(3):
        r = sh('git', 'push', '-q', '-f', 'origin', f'{c}:refs/heads/{BR}', cwd=WT)
        if r.returncode == 0:
            sh('git', 'update-ref', 'refs/remotes/origin/state', c, cwd=WT)
            return True
        print('state: push failed', (r.stderr or '')[-200:]); time.sleep(3)
    return False


def _signals_sig():
    """Подпись набора сигналов (то, что отдаёт /api/signals советнику): новые/закрытые сделки."""
    try:
        d = json.load(open(os.path.join(ST, 'pult_state.json'), encoding='utf-8'))
    except Exception:
        return ''
    out = []
    for k in sorted(d):
        r = d[k]
        if not k.endswith(('_A', '_C')) or not isinstance(r, dict) or not r.get('signal'): continue
        sg, note = r['signal'], str(r.get('note') or '')
        st = 'tp' if '→ TP' in note else 'sl' if '→ SL' in note else 'closed' if ('→ БУ' in note or 'закрыта в 22:00' in note) else 'open'
        out.append([k, sg.get('date'), sg.get('entry'), sg.get('stop'), sg.get('tp'), sg.get('side'), sg.get('be_at'), st])
    return hashlib.md5(json.dumps(out, ensure_ascii=False).encode()).hexdigest()


def _mirror_main():
    """Коммит состояния в main (как раньше). Возвращает True, если запушено."""
    sh('git', 'add', 'state')
    if sh('git', 'diff', '--cached', '--quiet').returncode == 0: return True
    sh('git', 'commit', '-q', '-m', 'state mirror ' + dt.datetime.utcnow().strftime('%H:%M UTC'))
    for _ in range(3):
        sh('git', 'pull', '-q', '--rebase', '--autostash', '-X', 'theirs', 'origin', 'main')
        if sh('git', 'push', '-q').returncode == 0: return True
        time.sleep(5)
    return False


def push():
    """Каждую минуту: состояние -> ветка state; в main — по условию (сигналы изменились / history.json / раз в MIRROR_SEC)."""
    mp = os.path.join(ST, 'mirror.json')
    try: mj = json.load(open(mp))
    except Exception: mj = {}
    sig = _signals_sig()
    hist = sh('git', 'status', '--porcelain', '--', 'state/history.json', 'state/journal.json').stdout.strip()
    now = int(time.time())
    need = bool(hist) or (MIRROR_SEC > 0 and (sig != mj.get('sig') or now - int(mj.get('ts', 0)) >= MIRROR_SEC))
    if need:
        json.dump(dict(ts=now, sig=sig), open(mp, 'w'))
    ok = _push_branch()
    if need: _mirror_main()
    return ok
