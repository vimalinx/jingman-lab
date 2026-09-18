"""Explicit Wi-Fi browser test server; keeps the default loopback server unchanged."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = Path(os.environ['LOCALAPPDATA']) / 'JingmanAcceptance'
STOP = DATA / 'phone-stop'
STATE = DATA / 'phone.json'
PORT = 8875


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'serve', 'stop'])
    parser.add_argument('--host')
    args = parser.parse_args()
    if args.action == 'stop':
        if STATE.exists():
            STOP.write_text('stop', encoding='utf-8')
            print('Phone test stop requested; data retained.')
        return
    try:
        address = ipaddress.IPv4Address(args.host)
        if not any(address in ipaddress.ip_network(n) for n in ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']):
            raise ValueError('Only a specific private LAN IPv4 address is allowed')
    except (ValueError, TypeError) as error:
        parser.error(str(error))
    host = str(address)
    if args.action == 'serve':
        import uvicorn
        from backend.app import create_app
        credentials = json.loads((DATA / 'app/credentials.json').read_text(encoding='utf-8'))
        app = create_app(DATA / 'app/jingman.sqlite3', **credentials, lab_enabled=True,
                         worker=False, web_dir=ROOT / 'web', allowed_hosts=[host],
                         lakala_mock_config=DATA / 'protocol/client.json')
        server = uvicorn.Server(uvicorn.Config(app, host=host, port=PORT, log_level='warning'))
        import threading
        def stop_when_requested():
            while not server.should_exit:
                if STOP.exists():
                    server.should_exit = True
                    return
                time.sleep(.5)
        threading.Thread(target=stop_when_requested, daemon=True).start()
        try:
            server.run()
        finally:
            if STATE.exists() and json.loads(STATE.read_text())['pid'] == os.getpid():
                STATE.unlink()
        return
    import socket
    with socket.socket() as probe:
        try:
            probe.bind((host, PORT))
        except OSError:
            parser.error('Phone port unavailable; existing listeners are not replaced.')
    STOP.unlink(missing_ok=True)
    with (DATA / 'phone.log').open('a', encoding='utf-8') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'serve', '--host', host],
                                 cwd=ROOT, stdout=log, stderr=log,
                                 env=dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1'),
                                 creationflags=subprocess.CREATE_NO_WINDOW)
    STATE.write_text(json.dumps({'pid': child.pid, 'host': host, 'port': PORT}), encoding='utf-8')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(80):
        if child.poll() is not None:
            raise SystemExit('Phone service failed. See phone.log.')
        try:
            with opener.open(f'http://{host}:{PORT}/api/health', timeout=.5) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(.2)
    else:
        raise SystemExit('Phone service startup timed out. See phone.log.')
    credentials = json.loads((DATA / 'app/credentials.json').read_text(encoding='utf-8'))
    print(f'http://{host}:{PORT}/#access={credentials["access_key"]}')


if __name__ == '__main__':
    main()
