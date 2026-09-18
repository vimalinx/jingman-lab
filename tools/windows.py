"""Windows acceptance launcher. All private state is outside the source tree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'JingmanAcceptance'
BASE = 'http://127.0.0.1:8874'


def healthy():
    expected = hashlib.sha256(str((DATA/'app/jingman.sqlite3').resolve()).encode()).hexdigest()[:16]
    try:
        with urllib.request.urlopen(BASE+'/api/health', timeout=1) as r:
            return json.load(r).get('instance') == expected
    except Exception:
        return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['start','serve','stop','status'], nargs='?', default='start')
    p.add_argument('--no-open', action='store_true')
    args = p.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    control = DATA/'stop-request'
    state = DATA/'run.json'
    if args.action == 'serve':
        # Only this supervisor's own Popen child tree is terminated.
        child = subprocess.Popen([sys.executable, '-u', '-m', 'backend.mock_demo', str(DATA), '--no-worker'], cwd=ROOT)
        state.write_text(json.dumps({'pid': os.getpid(), 'child_pid': child.pid, 'project': str(ROOT)}), encoding='utf-8')
        try:
            while child.poll() is None and not control.exists(): time.sleep(.4)
        finally:
            if child.poll() is None:
                # Windows does not propagate terminate() to the two child servers.
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'], capture_output=True)
            state.unlink(missing_ok=True)
            control.unlink(missing_ok=True)
        return
    if args.action == 'stop':
        if not state.exists():
            print('No owned running instance. Nothing stopped.'); return
        info = json.loads(state.read_text(encoding='utf-8'))
        if info.get('project') != str(ROOT): raise SystemExit('Different project owns this data; nothing stopped.')
        control.write_text('stop', encoding='utf-8')
        print('Stop requested; data and results are retained.'); return
    if args.action == 'status':
        print('READY' if healthy() else 'NOT RUNNING'); return
    if not healthy():
        for port in (8873,8874):
            with socket.socket() as sock:
                try: sock.bind(('127.0.0.1',port))
                except OSError: raise SystemExit(f'Port {port} is occupied by another service. Nothing stopped.')
        control.unlink(missing_ok=True)
        env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        with (DATA/'service.log').open('a', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'serve'], cwd=ROOT,
                stdout=log, stderr=log, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        for _ in range(120):
            if healthy(): break
            if process.poll() is not None: raise SystemExit('Startup failed. See '+str(DATA/'service.log'))
            time.sleep(.25)
        else: raise SystemExit('Startup timed out. See '+str(DATA/'service.log'))
    key = json.loads((DATA/'app/credentials.json').read_text(encoding='utf-8'))['access_key']
    url = BASE+'/acceptance.html#access='+key
    print('Project: '+str(ROOT/'miniprogram'))
    print('Backend: '+BASE)
    print('Acceptance: '+url)
    print('Local access key: '+key)
    if not args.no_open: webbrowser.open(url)


if __name__ == '__main__': main()
