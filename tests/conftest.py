import pytest
from fastapi.testclient import TestClient
from backend.app import create_app

KEY='integration-test-access-key-32bytes'
SECRET='integration-test-webhook-secret-not-production'
class Clock:
 def __init__(self):self.value=1788864000.0
 def __call__(self):return self.value
 def advance(self,seconds):self.value+=seconds

class Harness:
 def __init__(self,path):
  self.clock=Clock();self.app=create_app(path,KEY,SECRET,lab_enabled=True,clock=self.clock)
  self.c=TestClient(self.app);self.headers={}
  for name in ('customer','customer2','manager','picker','rider','other_store'):
   r=self.c.post('/api/session',json={'access_key':KEY,'persona':name});assert r.status_code==200,r.text
   self.headers[name]={'Authorization':'Bearer '+r.json()['token']}
 def request(self,method,path,body=None,who='customer',key=None,status=200):
  headers={**self.headers[who]}
  if key:headers['Idempotency-Key']=key
  r=self.c.request(method,path,headers=headers,json=body)
  assert r.status_code==status,(method,path,r.status_code,r.text)
  return r.json()
 def quote(self,items=None,**kwargs):
  who=kwargs.pop('who','customer')
  return self.request('POST','/api/quotes',{'items':items or [{'sku_id':101,'quantity':2}],'method':'pickup',**kwargs},who=who)
 def order(self,items=None,**kwargs):
  who=kwargs.pop('who','customer');q=self.quote(items,who=who,**kwargs)
  return self.request('POST','/api/orders',{'quote_id':q['id']},who=who,key='create-'+q['id'])
 def pay(self,o,**kw):return self.request('POST','/api/lab/pay/'+o['id'],{},**kw)['order']
 def accept(self,o):return self.request('POST','/api/admin/orders/'+o['id']+'/accept',{},who='picker')
 def pack(self,o):
  o=self.accept(o)
  for l in o['items']:
   self.request('POST','/api/admin/orders/'+o['id']+'/pick',{'line_id':l['id'],'quantity':l['quantity']-l['shortage_qty']},who='picker')
  return self.request('POST','/api/admin/orders/'+o['id']+'/ready',{},who='picker')
 def reconcile(self):return self.request('GET','/api/admin/reconciliation',who='manager')
 def worker(self):return self.request('POST','/api/lab/worker',{},who='manager')
 def sql(self,query,args=()):
  with self.app.state.db.read() as c:return [dict(r) for r in c.execute(query,args)]
 def product(self,sku=101):return self.request('GET',f'/api/products/{sku}')
 def sign(self,event):return self.app.state.sign(event)
 def callback(self,event,channel='payment',signature=None,status=200):
  from backend.service import dump
  r=self.c.post('/api/webhooks/'+channel,content=dump(event),headers={'Content-Type':'application/json','X-Lab-Signature':self.sign(event) if signature is None else signature})
  assert r.status_code==status,(r.status_code,r.text)
  return r.json()

@pytest.fixture
def h(tmp_path):
 harness=Harness(tmp_path/'jingman.sqlite3')
 yield harness
 harness.c.close()
