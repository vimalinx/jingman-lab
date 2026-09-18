"""Repeatable acceptance on isolated temporary databases; never clears user data."""
import argparse,subprocess,sys,tempfile,socket,time,json,os
from pathlib import Path
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parents[1]
os.environ['PYTHONUTF8']='1'
DEFAULT_EVIDENCE=(Path(os.environ['LOCALAPPDATA'])/'JingmanAcceptance'/'verification' if os.name=='nt' else ROOT/'output'/'verification')
E=Path(os.environ.get('JINGMAN_EVIDENCE_DIR',str(DEFAULT_EVIDENCE/time.strftime('%Y%m%d-%H%M%S')))).resolve()

def run(command,name,timeout=240):
 print('RUN',name,flush=True)
 with (E/(name+'.txt')).open('w',encoding='utf-8') as f:
  result=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 if result.returncode:
  print((E/(name+'.txt')).read_text(encoding='utf-8')[-8000:]);raise RuntimeError(name+' failed; see evidence/'+name+'.txt')
 print((E/(name+'.txt')).read_text(encoding='utf-8')[-600:],flush=True)

@contextmanager
def server(label):
 import httpx
 with tempfile.TemporaryDirectory(prefix='jingman-test-'+label+'-') as temp:
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  base=f'http://127.0.0.1:{port}'
  with open(os.devnull,'w') as log:
   child=subprocess.Popen([sys.executable,'-m','backend','--port',str(port),'--data-dir',temp,'--no-worker'],cwd=ROOT,stdout=log,stderr=log)
   try:
    for _ in range(150):
     if child.poll() is not None:raise RuntimeError('Acceptance server exited early')
     try:
      if httpx.get(base+'/api/health',timeout=.5).status_code==200:break
     except httpx.HTTPError:pass
     time.sleep(.1)
    else:raise RuntimeError('Acceptance server did not become ready')
    yield base,str(Path(temp)/'credentials.json')
   finally:
    child.terminate()
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:child.kill();child.wait()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--core',action='store_true',help='API/native/HTTP suites only; do not claim browser acceptance');ap.add_argument('--renderer',action='store_true',help='Explicit DOM renderer + live HTTP bridge, not browser networking');ap.add_argument('--http-only',action='store_true');args=ap.parse_args()
 E.mkdir(parents=True,exist_ok=False)
 os.environ['JINGMAN_EVIDENCE_DIR']=str(E)
 os.environ['JINGMAN_NATIVE_EVIDENCE_DIR']=str(E)
 if not args.http_only:
  run([sys.executable,'-m','pytest','-q','tests','--basetemp='+str(E/'pytest-data'),'-o','cache_dir='+str(E/'pytest-cache'),'--junitxml='+str(E/'api-final.xml')],'api-final')
  run(['node','tests/shopping_recovery.cjs'],'shopping-recovery')
  with server('native') as (base,creds):run(['node','tests/native_contract.cjs',base,creds],'native-final')
 with server('http') as (base,creds):run([sys.executable,'tests/http_concurrency.py','--base',base,'--credentials',creds],'http-final')
 if not args.core and not args.http_only:
  with server('browser') as (base,creds):
   cmd=[sys.executable,'tests/browser_scenarios.py','--base',base,'--credentials',creds]
   if args.renderer:cmd.append('--renderer')
   run(cmd,'browser-final')
 print('Requested suites completed. New evidence directory: '+str(E))
if __name__=='__main__':main()
