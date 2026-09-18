"""HTTP contract shared by the web verification UI and native WeChat client."""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, Header, HTTPException, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .db import Database
from .service import Retail, Problem, fail, row, rows, dump, identifier
from .fulfillment import pickup_restriction
from .payment_ports import payment_provider

class StrictModel(BaseModel):model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
class SessionInput(StrictModel):
 access_key:str=Field(min_length=12,max_length=200)
 persona:Literal['customer','customer2','manager','picker','rider','other_store']='customer'
class CartInput(StrictModel):
 sku_id:int
 quantity:int=Field(ge=0,le=99)
 selected:bool=True
 store_id:int=1
class Item(StrictModel):
 sku_id:int
 quantity:int=Field(ge=1,le=99)
class QuoteInput(StrictModel):
 store_id:int=1
 method:Literal['pickup','delivery']='pickup'
 address_id:int|None=None
 coupon_id:int|None=None
 items:list[Item]=Field(min_length=1,max_length=30)
 @model_validator(mode='after')
 def unique(self):
  if len({i.sku_id for i in self.items})!=len(self.items):raise ValueError('同一SKU不能重复提交')
  return self
class OrderInput(StrictModel):quote_id:str=Field(min_length=8,max_length=80)
class MockBarcodeInput(StrictModel):barcode:str=Field(pattern=r'^[0-9]{8,14}$')
class MockScenarioInput(StrictModel):
 scenario:Literal['success','empty','business-error','bad-signature','wrong-sid','stale','http203','timeout']
class PaymentInput(StrictModel):success:bool=True
class PaymentEvent(StrictModel):
 event_id:str=Field(min_length=4,max_length=100)
 timestamp:int
 order_id:str=Field(max_length=100)
 amount_cents:int=Field(gt=0)
 currency:str=Field(max_length=10)
 transaction_id:str=Field(max_length=150)
 status:str=Field(max_length=30)
class DeliveryEvent(StrictModel):
 event_id:str=Field(min_length=4,max_length=100)
 timestamp:int
 delivery_id:str=Field(max_length=100)
 status:Literal['accepted','picked_up','delivered']
 latitude:float|None=Field(default=None,ge=-90,le=90)
 longitude:float|None=Field(default=None,ge=-180,le=180)
class PickInput(StrictModel):
 line_id:int
 quantity:int=Field(ge=0,le=99)
class ShortageInput(PickInput):quantity:int=Field(ge=1,le=99)
class PickupInput(StrictModel):code:str=Field(pattern=r'^\d{6}$')
class AfterSaleInput(StrictModel):reason:str=Field(min_length=2,max_length=200)
class Approval(StrictModel):approve:bool=True
class AddressInput(StrictModel):
 name:str=Field(min_length=1,max_length=30)
 mobile:str=Field(pattern=r'^1\d{10}$')
 address:str=Field(min_length=4,max_length=160)
 latitude:float=Field(ge=-90,le=90)
 longitude:float=Field(ge=-180,le=180)
class Adjustment(StrictModel):
 sku_id:int
 delta:int=Field(ge=-10000,le=10000)
 reason:Literal['purchase','writeoff','pos_sale','return','stocktake']
 @model_validator(mode='after')
 def direction(self):
  if self.delta==0:raise ValueError('调整量不能为0')
  if self.reason in ('purchase','return') and self.delta<0:raise ValueError('入库量必须为正')
  if self.reason in ('writeoff','pos_sale') and self.delta>0:raise ValueError('出库量必须为负')
  return self
class ProductEdit(StrictModel):
 version:int=Field(ge=1)
 price_cents:int|None=Field(default=None,gt=0,le=10000000)
 active:bool|None=None
class FulfillmentInput(StrictModel):
 version:int=Field(ge=1)
 weight_g:int|None=Field(default=None,gt=0,le=1000000)
 pickup_only:bool|None=None
 @model_validator(mode='after')
 def changes(self):
  if not {'weight_g','pickup_only'} & self.model_fields_set:raise ValueError('请设置重量或履约方式')
  if 'pickup_only' in self.model_fields_set and self.pickup_only is None:raise ValueError('自提开关不能为空')
  return self
class ProductCreate(StrictModel):
 name:str=Field(min_length=2,max_length=60)
 category_id:int
 unit:str=Field(min_length=1,max_length=30)
 price_cents:int=Field(gt=0,le=10000000)
 quantity:int=Field(ge=0,le=10000)
 barcode:str=Field(pattern=r'^\d{8,14}$')
class SettingsInput(StrictModel):
 version:int=Field(ge=1)
 open:bool|None=None
 radius_km:float|None=Field(default=None,gt=0,le=50)
 minimum_cents:int|None=Field(default=None,ge=0,le=100000)
 delivery_cents:int|None=Field(default=None,ge=0,le=10000)
 free_shipping_cents:int|None=Field(default=None,ge=0,le=1000000)
class SwitchInput(StrictModel):
 key:Literal['printer_offline','refund_failure','delivery_unavailable']
 enabled:bool
class DeliveryRulesInput(StrictModel):
 version:int=Field(ge=1)
 start:str=Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
 end:str=Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
 rounding:Literal['ceil_kg','proportional']
 provisional_hours:bool
 provisional_rounding:bool
 @model_validator(mode='after')
 def ordered(self):
  if self.start>=self.end:raise ValueError('配送结束时间须晚于开始时间；暂不支持跨午夜')
  return self
class CategoryInput(StrictModel):name:str=Field(min_length=2,max_length=30)
class CouponInput(StrictModel):
 user_id:int
 minimum_cents:int=Field(ge=1,le=1000000)
 discount_cents:int=Field(gt=0,le=100000)
 @model_validator(mode='after')
 def discount(self):
  if self.discount_cents>=self.minimum_cents:raise ValueError('优惠额应小于门槛')
  return self

PERSONAS={'customer':1,'customer2':2,'manager':10,'picker':11,'rider':12,'other_store':20}

def create_app(db_path:str|Path,access_key:str,webhook_secret:str,*,lab_enabled=False,clock=time.time,worker=False,web_dir=None,allowed_hosts=None,lakala_mock_config=None):
 if not lab_enabled:raise RuntimeError('Local integration laboratory only. Explicit lab_enabled is required; there is no production mode.')
 if len(access_key)<24 or len(webhook_secret)<32:raise RuntimeError('Random laboratory access key and webhook secret required')
 db=Database(db_path,clock);db.initialize();engine=Retail(db)
 payments=payment_provider(engine)
 @asynccontextmanager
 async def lifespan(app):
  async def work():
   while True:
    await asyncio.sleep(3)
    try:await asyncio.to_thread(engine.drain)
    except Exception as error:
     # Do not silently mark a failed queue batch successful.
     import logging;logging.getLogger('jingman.worker').exception('Worker batch failed: %s',error)
  task=asyncio.create_task(work()) if worker else None
  yield
  if task:
   task.cancel()
   try:await task
   except asyncio.CancelledError:pass
 app=FastAPI(title='京漫便民 · 本地联调 API',version='0.2.0',description='真实 SQLite 事务；支付、POS、配送、打印为明确的模拟适配器。不能用于公网收款。',lifespan=lifespan,docs_url=None,redoc_url=None)
 app.state.db=db;app.state.engine=engine;app.state.sign=lambda payload:hmac.new(webhook_secret.encode(),dump(payload).encode(),hashlib.sha256).hexdigest()
 app.add_middleware(TrustedHostMiddleware,allowed_hosts=allowed_hosts or ['localhost','127.0.0.1','[::1]','testserver'])
 @app.middleware('http')
 async def security(request,call_next):
  if request.headers.get('content-length','0').isdigit() and int(request.headers.get('content-length','0'))>131072:
   return JSONResponse({'error':{'code':'body_too_large','message':'请求体过大'}},status_code=413)
  response=await call_next(request)
  response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY';response.headers['Referrer-Policy']='no-referrer'
  if request.url.path.startswith('/api'):response.headers['Cache-Control']='no-store'
  response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
  return response
 @app.exception_handler(Problem)
 async def problem_handler(request,error):return JSONResponse({'error':{'code':error.code,'message':error.message}},status_code=error.status)
 @app.exception_handler(RequestValidationError)
 async def validation_handler(request,error):
  return JSONResponse({'error':{'code':'invalid_input','message':'输入格式或数值不正确','fields':[{'path':'.'.join(str(p) for p in e['loc']),'message':e['msg']} for e in error.errors()]}},status_code=422)
 @app.exception_handler(sqlite3.IntegrityError)
 async def integrity_handler(request,error):return JSONResponse({'error':{'code':'constraint_conflict','message':'数据约束冲突；本次操作已回滚'}},status_code=409)
 def auth(authorization:str|None=Header(default=None)):
  if not authorization or not authorization.startswith('Bearer '):fail(401,'unauthenticated','请先登录体验账号')
  token=authorization[7:]
  with db.read() as c:
   r=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),db.clock())).fetchone()
   if not r:fail(401,'session_expired','登录状态已过期，请重新进入')
   return dict(r)
 def customer(actor=Depends(auth)):
  if actor['role']!='customer':fail(403,'customer_only','此接口仅供顾客使用')
  return actor
 def staff(actor=Depends(auth)):
  if actor['role'] not in ('manager','picker','rider'):fail(403,'staff_only','此接口需要店员身份')
  return actor
 def manager(actor=Depends(staff)):
  if actor['role']!='manager':fail(403,'manager_only','此操作需要店长权限')
  return actor
 def operator(actor=Depends(manager)):
  if actor['id']!=10:fail(403,'operator_only','此操作仅限本地实验室管理员')
  return actor
 def idem(idempotency_key:str|None=Header(default=None)):
  if not idempotency_key or not 8<=len(idempotency_key)<=128 or not all(ch.isalnum() or ch in '-_:' for ch in idempotency_key):fail(422,'idempotency_key','请提供8至128位幂等键')
  return idempotency_key
 failures={}
 @app.post('/api/session')
 def login(data:SessionInput,request:Request):
  host=request.client.host if request.client else 'unknown';now=db.clock();recent=[t for t in failures.get(host,[]) if now-t<60]
  if len(recent)>=10:fail(429,'rate_limit','验证失败次数过多，请一分钟后重试')
  if not secrets.compare_digest(data.access_key,access_key):
   failures[host]=recent+[now];fail(401,'bad_lab_key','请输入启动终端显示的实验室访问口令')
  failures.pop(host,None);token=secrets.token_urlsafe(32)
  with db.tx() as c:
   actor=row(c,'SELECT * FROM users WHERE id=?',(PERSONAS[data.persona],));c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),actor['id'],now+3600*12))
  return {'token':token,'user':actor,'lab':True,'expires':now+3600*12}
 @app.delete('/api/session')
 def logout(actor=Depends(auth),authorization:str=Header()):
  with db.tx() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(authorization[7:].encode()).hexdigest(),))
  return {'ok':True}
 @app.get('/api/health')
 def health():return {'ok':True,'mode':'local-laboratory','version':'0.2.0','database':'SQLite','external_providers':'simulated','instance':hashlib.sha256(str(Path(db.path).resolve()).encode()).hexdigest()[:16]}
 @app.get('/api/store')
 def store(store_id:int=1):
  with db.read() as c:
   result=row(c,'SELECT * FROM stores WHERE id=?',(store_id,))
   profile=c.execute('SELECT public_json FROM store_profile WHERE store_id=?',(store_id,)).fetchone()
   if profile:result.update(json.loads(profile['public_json']))
   return result
 @app.post('/api/admin/lakala-mock/query')
 def mock_barcode(data:MockBarcodeInput,actor=Depends(manager)):
  if not lakala_mock_config:fail(409,'mock_disabled','本地协议模拟未配置，请按模拟接入指南启动；不是拉卡拉授权失败')
  if actor['store_id']!=1:fail(403,'mock_store','模拟服务仅提供独立测试门店1')
  from .lakala_mock import query_local
  from .lakala_readonly import IntegrationBlocked
  import httpx
  try:return query_local(lakala_mock_config,data.barcode)
  except httpx.TimeoutException:fail(504,'mock_timeout','本地模拟查询超时；未自动重试、未写库存')
  except (IntegrationBlocked,ValueError,OSError,KeyError,httpx.HTTPError):
   fail(502,'mock_rejected','本地模拟连接或验签未通过；未导入商品、未写库存。请核对服务场景与配置。')
 @app.put('/api/admin/lakala-mock/scenario')
 def mock_scenario(data:MockScenarioInput,actor=Depends(operator)):
  if not lakala_mock_config:fail(409,'mock_disabled','本地模拟服务未配置')
  from .lakala_mock import load_config
  load_config(lakala_mock_config)
  destination=Path(lakala_mock_config).parent/'scenario.json'
  temporary=destination.with_suffix('.tmp')
  temporary.write_text(dump({'scenario':data.scenario}),encoding='utf-8')
  temporary.replace(destination)
  return {'mock':True,'scenario':data.scenario,'real_provider_called':False}
 @app.get('/api/admin/import-review')
 def import_review(actor=Depends(manager)):
  with db.read() as c:
   result=rows(c,'SELECT p.id,p.name,p.barcode,s.source_row,s.source_stock,s.weighed,s.review_json FROM product_sources s JOIN products p ON p.id=s.sku_id JOIN inventory i ON i.sku_id=p.id WHERE i.store_id=? ORDER BY s.source_row',(actor['store_id'],))
   for item in result:
    item['source_review_json']=item['review_json']
    item['review_json']=dump(engine.review_issues(c,item['id'],actor['store_id']))
   return result
 @app.get('/assets/catalog/{sku}.webp')
 def product_image(sku:int):
  target=Path(db.path).parent/'product-images'/f'{sku}.webp'
  if not target.is_file():
   return FileResponse(Path(__file__).resolve().parents[1]/'web/assets/placeholder.svg',media_type='image/svg+xml')
  return FileResponse(target,media_type='image/webp')
 @app.get('/assets/placeholder.webp')
 def placeholder():
  return FileResponse(Path(__file__).resolve().parents[1]/'web/assets/placeholder.svg',media_type='image/svg+xml')
 @app.get('/api/categories')
 def categories():
  with db.read() as c:return rows(c,'SELECT * FROM categories ORDER BY sort,id')
 @app.get('/api/products')
 def catalog(store_id:int=1,q:str='',category_id:int|None=None):
  if len(q)>100:fail(422,'query_length','搜索词过长')
  return engine.catalog(store_id,q,category_id)
 @app.get('/api/products/{sku}')
 def product(sku:int,store_id:int=1):
  products=engine.catalog(store_id)
  for p in products:
   if p['id']==sku:return {**p,'variants':[v for v in products if v['family']==p['family']]}
  fail(404,'not_found','商品不存在')
 @app.get('/api/catalog-page')
 def catalog_page(store_id:int=1,q:str=Query('',max_length=100),category_id:int|None=None,
                  page:int=Query(1,ge=1),page_size:int=Query(24,ge=1,le=100)):
  return engine.catalog(store_id,q,category_id,page,page_size)
 @app.get('/api/cart')
 def cart(store_id:int=1,actor=Depends(customer)):return engine.cart(actor,store_id)
 @app.put('/api/cart')
 def cart_set(data:CartInput,actor=Depends(customer)):return engine.set_cart(actor,data.sku_id,data.quantity,data.selected,data.store_id)
 @app.get('/api/favorites')
 def favorites(actor=Depends(customer)):
  with db.read() as c:return [r['sku_id'] for r in c.execute('SELECT sku_id FROM favorites WHERE user_id=?',(actor['id'],))]
 @app.put('/api/favorites/{sku}')
 def favorite(sku:int,actor=Depends(customer)):
  with db.tx() as c:
   row(c,'SELECT id FROM products WHERE id=?',(sku,));exists=c.execute('SELECT 1 FROM favorites WHERE user_id=? AND sku_id=?',(actor['id'],sku)).fetchone()
   if exists:c.execute('DELETE FROM favorites WHERE user_id=? AND sku_id=?',(actor['id'],sku))
   else:c.execute('INSERT INTO favorites VALUES(?,?)',(actor['id'],sku))
  return {'selected':not bool(exists)}
 @app.get('/api/addresses')
 def addresses(actor=Depends(customer)):
  with db.read() as c:return rows(c,'SELECT * FROM addresses WHERE user_id=? ORDER BY id',(actor['id'],))
 @app.post('/api/addresses')
 def address_add(data:AddressInput,actor=Depends(customer)):
  with db.tx() as c:
   if c.execute('SELECT COUNT(*) FROM addresses WHERE user_id=?',(actor['id'],)).fetchone()[0]>=20:fail(422,'address_limit','最多保留20个地址')
   cursor=c.execute('INSERT INTO addresses(user_id,name,mobile,address,latitude,longitude) VALUES(?,?,?,?,?,?)',(actor['id'],data.name,data.mobile,data.address,data.latitude,data.longitude));return row(c,'SELECT * FROM addresses WHERE id=?',(cursor.lastrowid,))
 @app.put('/api/addresses/{aid}')
 def address_edit(aid:int,data:AddressInput,actor=Depends(customer)):
  with db.tx() as c:
   row(c,'SELECT * FROM addresses WHERE id=? AND user_id=?',(aid,actor['id']))
   c.execute('UPDATE addresses SET name=?,mobile=?,address=?,latitude=?,longitude=? WHERE id=?',(data.name,data.mobile,data.address,data.latitude,data.longitude,aid));return row(c,'SELECT * FROM addresses WHERE id=?',(aid,))
 @app.delete('/api/addresses/{aid}')
 def address_delete(aid:int,actor=Depends(customer)):
  with db.tx() as c:
   row(c,'SELECT * FROM addresses WHERE id=? AND user_id=?',(aid,actor['id']));c.execute('DELETE FROM addresses WHERE id=?',(aid,))
  return {'ok':True}
 @app.get('/api/coupons')
 def coupons(actor=Depends(customer)):
  with db.read() as c:
   result=rows(c,'SELECT * FROM coupons WHERE user_id=? ORDER BY id',(actor['id'],))
   for v in result:v['expired']=v['expires']<=db.clock()
   return result
 @app.get('/api/notifications')
 def notifications(actor=Depends(customer)):
  with db.read() as c:return rows(c,'SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50',(actor['id'],))
 @app.post('/api/quotes')
 def quote(data:QuoteInput,actor=Depends(customer)):return engine.quote(actor,data.model_dump())
 @app.post('/api/orders')
 def order_create(data:OrderInput,actor=Depends(customer),key=Depends(idem)):return engine.create_order(actor,data.quote_id,key)
 @app.get('/api/orders')
 def orders(actor=Depends(auth)):
  if actor['role']=='rider':fail(403,'rider_scope','配送员请使用配送任务接口')
  return engine.list_orders(actor)
 @app.get('/api/orders/{oid}')
 def order_get(oid:str,actor=Depends(auth)):
  if actor['role']=='rider':fail(403,'rider_scope','配送员请使用配送任务接口')
  return engine.order(actor,oid)
 @app.post('/api/orders/{oid}/cancel')
 def cancel(oid:str,actor=Depends(auth)):return engine.cancel(actor,oid)
 def verify_payload(raw:bytes,signature:str,model):
  expected=hmac.new(webhook_secret.encode(),raw,hashlib.sha256).hexdigest()
  if not signature or not hmac.compare_digest(expected,signature):fail(401,'bad_signature','模拟回调签名校验失败')
  try:data=model.model_validate_json(raw).model_dump(exclude_none=True)
  except ValidationError:fail(422,'invalid_event','回调格式不合法')
  if abs(db.clock()-data['timestamp'])>300:fail(401,'stale_event','回调时间戳超出有效窗口')
  return data
 @app.post('/api/webhooks/payment')
 async def payment_webhook(request:Request,x_lab_signature:str=Header(default='')):
  return engine.payment_event(verify_payload(await request.body(),x_lab_signature,PaymentEvent))
 @app.post('/api/webhooks/delivery')
 async def delivery_webhook(request:Request,x_lab_signature:str=Header(default='')):
  return engine.delivery_event(verify_payload(await request.body(),x_lab_signature,DeliveryEvent))
 @app.post('/api/lab/gateway/charge/{oid}')
 def gateway(oid:str,data:PaymentInput,actor=Depends(customer)):
  event=engine.gateway_charge(actor,oid,data.success);return {'event':event,'signature':app.state.sign(event)}
 @app.post('/api/lab/pay/{oid}')
 @app.post('/api/payments/{oid}/simulate')
 def mock_pay(oid:str,data:PaymentInput,actor=Depends(customer)):
  event=payments.create_payment(actor,oid,success=data.success);validated=verify_payload(dump(event).encode(),app.state.sign(event),PaymentEvent)
  result=engine.payment_event(validated);return {'callback':result,'order':engine.order(actor,oid),'simulated':True}
 @app.get('/api/payments/{oid}')
 def payment_status(oid:str,actor=Depends(customer)):
  return payments.query_payment(actor,oid)
 @app.post('/api/payments/{oid}/prepay')
 def real_prepay(oid:str,actor=Depends(customer)):
  engine.order(actor,oid)
  fail(503,'payment_not_configured','预留真实支付接口，尚未配置；请使用明确标识的模拟支付')
 @app.post('/api/payments/wechat/notify')
 @app.post('/api/payments/wechat/refund-notify')
 async def real_notify(request:Request):
  fail(503,'payment_not_configured','真实支付回调验签解密尚未接入，不接收付款成功通知')
 @app.post('/api/orders/{oid}/aftersale')
 def aftersale(oid:str,data:AfterSaleInput,actor=Depends(customer),key=Depends(idem)):return engine.request_aftersale(actor,oid,data.reason,key)
 @app.post('/api/admin/orders/{oid}/accept')
 def accept(oid:str,actor=Depends(staff)):return engine.accept(actor,oid)
 @app.post('/api/admin/orders/{oid}/pick')
 def pick(oid:str,data:PickInput,actor=Depends(staff)):return engine.pick(actor,oid,data.line_id,data.quantity)
 @app.post('/api/admin/orders/{oid}/shortage')
 def shortage(oid:str,data:ShortageInput,actor=Depends(staff),key=Depends(idem)):return engine.shortage(actor,oid,data.line_id,data.quantity,key)
 @app.post('/api/admin/orders/{oid}/ready')
 def ready(oid:str,actor=Depends(staff)):return engine.ready(actor,oid)
 @app.post('/api/admin/orders/{oid}/pickup')
 def pickup(oid:str,data:PickupInput,actor=Depends(staff)):return engine.verify_pickup(actor,oid,data.code)
 @app.post('/api/admin/orders/{oid}/dispatch')
 def dispatch(oid:str,actor=Depends(staff)):return engine.dispatch(actor,oid)
 @app.get('/api/rider/tasks')
 def tasks(actor=Depends(staff)):
  with db.read() as c:
   result=rows(c,'SELECT d.*,o.number,o.address_json FROM deliveries d JOIN orders o ON o.id=d.order_id WHERE o.store_id=? ORDER BY d.created DESC',(actor['store_id'],))
   for r in result:
    a=json.loads(r.pop('address_json'));r['address']=a.get('address','');r['contact']=a.get('name','');phone=a.get('mobile','');r['mobile_masked']=phone[:3]+'****'+phone[-4:] if phone else ''
   return result
 @app.post('/api/lab/delivery/{did}/{state}')
 def advance_delivery(did:str,state:Literal['accepted','picked_up','delivered'],actor=Depends(staff)):
  with db.read() as c:
   d=row(c,'SELECT * FROM deliveries WHERE id=?',(did,));o=engine.order_access(c,actor,d['order_id']);engine.staff_scope(actor,o['store_id'],('manager','rider'))
  event={'event_id':identifier('evt'),'timestamp':int(db.clock()),'delivery_id':did,'status':state}
  result=engine.delivery_event(verify_payload(dump(event).encode(),app.state.sign(event),DeliveryEvent));return {'callback':result,'simulated':True}
 @app.post('/api/admin/refunds/{rid}/approve')
 def approve(rid:str,data:Approval,actor=Depends(manager)):return engine.approve_refund(actor,rid,data.approve)
 @app.get('/api/admin/dashboard')
 def dashboard(actor=Depends(staff)):return engine.dashboard(actor)
 @app.post('/api/admin/inventory/adjust')
 def adjust(data:Adjustment,actor=Depends(manager),key=Depends(idem)):return engine.adjust_inventory(actor,data.sku_id,data.delta,data.reason,key)
 @app.patch('/api/admin/products/{sku}')
 def edit(sku:int,data:ProductEdit,actor=Depends(manager)):return engine.edit_product(actor,sku,data.model_dump(exclude_none=True))
 @app.patch('/api/admin/products/{sku}/fulfillment')
 def edit_fulfillment(sku:int,data:FulfillmentInput,actor=Depends(manager)):
  return engine.edit_fulfillment(actor,sku,data.model_dump(exclude_unset=True))
 @app.post('/api/admin/products')
 def add_product(data:ProductCreate,actor=Depends(manager)):
  with db.tx() as c:
   category=row(c,'SELECT * FROM categories WHERE id=?',(data.category_id,))
   sku=c.execute('SELECT COALESCE(MAX(id),100)+1 FROM products').fetchone()[0]
   c.execute('INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?)',(sku,'custom-'+str(sku),data.name,data.category_id,data.unit,'店长在本地演练中添加的商品。','daily','新品',data.barcode))
   c.execute('INSERT INTO inventory VALUES(?,?,?,?,0,0,1,1)',(actor['store_id'],sku,data.price_cents,data.price_cents))
   reason=pickup_restriction(data.name,category['name'].split(' / '))
   c.execute('INSERT INTO product_fulfillment VALUES(?,?,NULL,?,?)',(actor['store_id'],sku,int(bool(reason)),reason))
   if data.quantity:engine.stock(c,actor['store_id'],sku,data.quantity,0,'purchase','new-product')
   engine.audit(c,actor,'product.created',sku)
  return next(p for p in engine.catalog(actor['store_id']) if p['id']==sku)
 @app.patch('/api/admin/store')
 def settings(data:SettingsInput,actor=Depends(manager)):return engine.store_settings(actor,data.model_dump(exclude_none=True))
 @app.patch('/api/admin/delivery-rules')
 def delivery_rules(data:DeliveryRulesInput,actor=Depends(manager)):return engine.delivery_rules(actor,data.model_dump())
 @app.get('/api/admin/audit')
 def audit(actor=Depends(manager)):
  with db.read() as c:return rows(c,'SELECT * FROM audit WHERE store_id=? ORDER BY id DESC LIMIT 1000',(actor['store_id'],))
 @app.get('/api/admin/stock-ledger')
 def ledger(actor=Depends(manager)):
  with db.read() as c:return rows(c,'SELECT * FROM stock_ledger WHERE store_id=? ORDER BY id DESC LIMIT 1000',(actor['store_id'],))
 @app.get('/api/admin/reconciliation')
 def reconcile(actor=Depends(manager)):return engine.reconciliation(actor)
 @app.get('/api/admin/print-receipts')
 def receipts(actor=Depends(manager)):
  with db.read() as c:return rows(c,'SELECT p.* FROM print_receipts p JOIN orders o ON o.id=p.order_id WHERE o.store_id=? ORDER BY p.id DESC',(actor['store_id'],))
 @app.post('/api/admin/categories')
 def category_add(data:CategoryInput,actor=Depends(operator)):
  with db.tx() as c:
   cursor=c.execute('INSERT INTO categories(name,sort) VALUES(?,99)',(data.name,));engine.audit(c,actor,'category.created',cursor.lastrowid);return row(c,'SELECT * FROM categories WHERE id=?',(cursor.lastrowid,))
 @app.post('/api/admin/coupons')
 def issue_coupon(data:CouponInput,actor=Depends(operator)):
  with db.tx() as c:
   u=row(c,'SELECT * FROM users WHERE id=?',(data.user_id,))
   if u['role']!='customer':fail(422,'not_customer','只能向顾客发券')
   cursor=c.execute('INSERT INTO coupons(user_id,title,minimum_cents,discount_cents,expires) VALUES(?,?,?,?,?)',(data.user_id,f'门店赠券 · 满{data.minimum_cents/100:g}减{data.discount_cents/100:g}',data.minimum_cents,data.discount_cents,db.clock()+86400*30));engine.audit(c,actor,'coupon.issued',cursor.lastrowid);return {'id':cursor.lastrowid}
 @app.get('/api/admin/members')
 def members(actor=Depends(manager)):
  with db.read() as c:return rows(c,'SELECT u.id,u.name,COUNT(o.id) orders,COALESCE(SUM(o.paid_cents-o.refunded_cents),0) net_cents FROM users u JOIN orders o ON o.user_id=u.id AND o.store_id=? GROUP BY u.id ORDER BY net_cents DESC',(actor['store_id'],))
 @app.get('/api/lab/state')
 def state(actor=Depends(operator)):
  with db.read() as c:return {'switches':{r['key']:bool(r['value']) for r in c.execute('SELECT * FROM switches')},'outbox':rows(c,'SELECT * FROM outbox ORDER BY id DESC LIMIT 100'),'gateway_ledger':rows(c,'SELECT * FROM gateway_ledger ORDER BY id DESC LIMIT 100'),'refunds':rows(c,'SELECT * FROM refunds ORDER BY created DESC LIMIT 100')}
 @app.put('/api/lab/switch')
 def switch(data:SwitchInput,actor=Depends(operator)):
  with db.tx() as c:c.execute('UPDATE switches SET value=? WHERE key=?',(int(data.enabled),data.key));engine.audit(c,actor,'lab.switch',data.key,{'enabled':data.enabled})
  return {'ok':True}
 @app.post('/api/lab/worker')
 def drain(actor=Depends(operator)):return engine.drain()
 @app.post('/api/lab/sample-order')
 def sample_order(actor=Depends(operator),key=Depends(idem)):
  with db.read() as c:buyer=row(c,'SELECT * FROM users WHERE id=1')
  sample_key='sample:'+key
  with db.read() as c: prior=c.execute("SELECT result_id FROM idempotency WHERE user_id=1 AND scope='order' AND key=?",(sample_key,)).fetchone()
  if prior: o=engine.order(buyer,prior['result_id'])
  else:
   q=engine.quote(buyer,{'store_id':1,'method':'delivery','address_id':1,'coupon_id':None,'items':[{'sku_id':101,'quantity':2},{'sku_id':110,'quantity':1}]})
   try: o=engine.create_order(buyer,q['id'],sample_key)
   except Problem as exc:
    if exc.code!='key_conflict': raise
    with db.read() as c: prior=row(c,"SELECT result_id FROM idempotency WHERE user_id=1 AND scope='order' AND key=?",(sample_key,))
    o=engine.order(buyer,prior['result_id'])
  event=engine.gateway_charge(buyer,o['id'])
  engine.payment_event(verify_payload(dump(event).encode(),app.state.sign(event),PaymentEvent))
  return {'order_id':o['id'],'simulated':True}
 @app.get('/api/admin/export')
 def export(actor=Depends(manager)):
  report=engine.reconciliation(actor)
  with db.read() as c:report['orders']=rows(c,'SELECT number,state,subtotal_cents,discount_cents,shipping_cents,total_cents,paid_cents,refunded_cents FROM orders WHERE store_id=? ORDER BY created',(actor['store_id'],))
  return JSONResponse(report,headers={'Content-Disposition':'attachment; filename="jingman-reconciliation.json"'})
 @app.get('/docs',include_in_schema=False)
 def offline_docs():return RedirectResponse('/api-reference.html')
 @app.get('/api/contract')
 def contract():return {'money_unit':'fen','order_expiry_seconds':900,'quote_expiry_seconds':120,'delivery_policy':'discounted_merchandise_threshold','providers':'HMAC-SHA256 MOCK adapters, not WeChat API v3','database':'SQLite WAL','production_enabled':False}
 if web_dir:app.mount('/',StaticFiles(directory=str(web_dir),html=True),name='web')
 return app
