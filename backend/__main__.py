"""python -m backend: explicit local-only launcher with private persistent state."""
import argparse,json,os,secrets,sys
from pathlib import Path
import uvicorn
from .app import create_app

def main():
 p=argparse.ArgumentParser(description='京漫便民 · 本地联调实验室（不真实收款）')
 p.add_argument('--port',type=int,default=8765)
 p.add_argument('--data-dir',type=Path,default=Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'jingman-lab')
 p.add_argument('--no-worker',action='store_true',help='手动驱动模拟回调任务')
 p.add_argument('--lakala-mock-config',type=Path,help='源码外专用本机协议模拟client.json；不接受商家配置')
 args=p.parse_args()
 os.umask(0o077)
 if os.environ.get('JINGMAN_ENV','lab')!='lab':p.error('此交付仅允许 lab 模式；没有生产收款模式。')
 args.data_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
 os.chmod(args.data_dir,0o700)
 keyfile=args.data_dir/'credentials.json'
 if not keyfile.exists():
  fd=os.open(keyfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,'w') as f:json.dump({'access_key':secrets.token_urlsafe(24),'webhook_secret':secrets.token_urlsafe(32)},f)
 cfg=json.loads(keyfile.read_text())
 if args.lakala_mock_config:
  from .lakala_mock import load_config
  load_config(args.lakala_mock_config)
 app=create_app(args.data_dir/'jingman.sqlite3',**cfg,lab_enabled=True,worker=not args.no_worker,web_dir=Path(__file__).resolve().parents[1]/'web',lakala_mock_config=args.lakala_mock_config)
 print('\n京漫便民 · 本地联调实验室\n所有金额均为演练数据，不真实扣款。仅监听本机。',flush=True)
 print(f'打开：http://127.0.0.1:{args.port}/#access={cfg["access_key"]}',flush=True)
 print(f'原生小程序本机联调口令：{cfg["access_key"]}\n数据目录：{args.data_dir}\n',flush=True)
 uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='warning')
if __name__=='__main__':main()
