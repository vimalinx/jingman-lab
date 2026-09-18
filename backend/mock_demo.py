"""Own both local demo processes; Ctrl+C only stops children started here."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from .lakala_mock import initialize, load_config, query_local
from .lakala_readonly import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--no-worker', action='store_true', help='人工验收时在实验室页面手动重试任务')
    args = parser.parse_args()
    directory = args.directory
    if not directory.is_absolute() or directory.resolve().is_relative_to(ROOT):
        parser.error('模拟数据须放到源码之外的绝对目录')
    os.umask(0o077)
    # Fail closed before generating state; never kill or reuse a foreign listener.
    for port in (8873, 8874):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                parser.error(f'端口{port}已占用；不会停止已有服务。若是当前模拟服务，可直接继续使用。')
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if directory.is_symlink() or (os.name != 'nt' and (directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077)):
        parser.error('模拟目录须由当前用户拥有、非符号链接且权限0700')
    protocol = directory / 'protocol'
    if not protocol.exists():
        initialize(protocol, 8873)
    config = load_config(protocol / 'client.json')
    if config['base_url'] != 'http://127.0.0.1:8873/b2c-oms-server':
        parser.error('一键演练固定使用8873/8874，已有配置不匹配')
    children = []
    try:
        mock = subprocess.Popen([sys.executable, '-m', 'backend.lakala_mock', 'serve',
                                 '--config', str(protocol / 'server.json')], cwd=ROOT)
        children.append(mock)
        for attempt in range(40):
            if mock.poll() is not None:
                raise RuntimeError('模拟协议服务启动失败')
            with socket.socket() as sock:
                ready = sock.connect_ex(('127.0.0.1', 8873)) == 0
            if ready:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('模拟协议服务启动超时')
        query_local(protocol / 'client.json', '9900000000001')
        print('本地协议模拟验签通过。下方为京漫实验室地址和口令；所有数据均为模拟。', flush=True)
        app = subprocess.Popen([sys.executable, '-m', 'backend', '--port', '8874',
                                '--data-dir', str(directory / 'app'), '--lakala-mock-config',
                                str(protocol / 'client.json')] + (['--no-worker'] if args.no_worker else []), cwd=ROOT)
        children.append(app)
        while all(child.poll() is None for child in children):
            time.sleep(.5)
        raise RuntimeError('一个模拟服务已退出；停止本次启动的另一个服务')
    except KeyboardInterrupt:
        print('\n已停止本次演练进程，模拟数据保留。')
    except Exception as error:
        print(f'演练启动或运行失败：{type(error).__name__}；未访问真实拉卡拉。', file=sys.stderr)
        return 2
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
