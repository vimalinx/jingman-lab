"""Actual localhost HTTP concurrency verification; requires a fresh test database."""
import argparse,json,time,statistics,os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);ap.add_argument('--credentials',required=True);args=ap.parse_args()
 root=Path(__file__).resolve().parents[1];key=json.loads(Path(args.credentials).read_text())['access_key']
 client=httpx.Client(base_url=args.base,timeout=25,limits=httpx.Limits(max_connections=60,max_keepalive_connections=60))
 def session(who):
  r=client.post('/api/session',json={'access_key':key,'persona':who});r.raise_for_status();return {'Authorization':'Bearer '+r.json()['token']}
 customer=session('customer');manager=session('manager')
 def req(method,path,headers=customer,body=None):
  r=client.request(method,path,headers=headers,json=body);r.raise_for_status();return r.json()
 products=req('GET','/api/products');banana=next(p for p in products if p['id']==101)
 assert banana['on_hand']==48,'Use a fresh disposable database'
 req('POST','/api/admin/inventory/adjust',{**manager,'Idempotency-Key':'load-set-last-item'},{'sku_id':101,'delta':-47,'reason':'writeoff'})
 quotes=[req('POST','/api/quotes',body={'items':[{'sku_id':101,'quantity':1}],'method':'pickup','store_id':1}) for _ in range(40)]
 def order(q):
  t=time.perf_counter();r=client.post('/api/orders',headers={**customer,'Idempotency-Key':'http-race-'+q['id']},json={'quote_id':q['id']});return r,time.perf_counter()-t
 started=time.perf_counter()
 with ThreadPoolExecutor(max_workers=40) as pool:results=list(pool.map(order,quotes))
 counts={str(code):sum(r.status_code==code for r,_ in results) for code in {r.status_code for r,_ in results}}
 assert counts=={'200':1,'409':39},counts
 oid=next(r.json()['id'] for r,_ in results if r.status_code==200)
 def pay(_):return client.post('/api/lab/pay/'+oid,headers=customer,json={})
 with ThreadPoolExecutor(max_workers=24) as pool:paid=list(pool.map(pay,range(24)))
 assert all(r.status_code==200 for r in paid),[r.text for r in paid if r.status_code!=200]
 req('POST','/api/lab/worker',manager,{})
 labs=req('GET','/api/lab/state',manager);report=req('GET','/api/admin/reconciliation',manager);prints=req('GET','/api/admin/print-receipts',manager)
 product=next(p for p in req('GET','/api/products') if p['id']==101)
 assert product['on_hand']==0 and product['reserved']==0
 assert len([e for e in labs['gateway_ledger'] if e['kind']=='charge'])==1
 assert len(prints)==1 and report['ok']
 outcome={'passed':True,'transport':'real HTTP on loopback via uvicorn','database':'SQLite WAL','checkout_requests':40,'checkout_statuses':counts,'duplicate_payment_requests':24,'payment_success_responses':24,'charges':1,'stock_on_hand':product['on_hand'],'stock_reserved':product['reserved'],'printed_receipts':len(prints),'reconciliation':report,'elapsed_seconds':round(time.perf_counter()-started,3),'note':'This is a functional concurrency experiment, not a production capacity benchmark.'}
 out=Path(os.environ.get('JINGMAN_EVIDENCE_DIR',str(root/'evidence')));out.mkdir(parents=True,exist_ok=True)
 (out/'http-concurrency.json').write_text(json.dumps(outcome,ensure_ascii=False,indent=2));print(json.dumps(outcome,ensure_ascii=False,indent=2));client.close()
if __name__=='__main__':main()
