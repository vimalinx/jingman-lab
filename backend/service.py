"""Transactional retail engine for the Jingman local integration laboratory.

All amounts are integer fen. SQLite is the source of truth; the web and WeChat
clients cannot set prices, payment status, stock counts or staff identities.
External-provider records are deliberately simulated, never real WeChat money.
"""
from __future__ import annotations
import hashlib
import json
import math
import secrets
import sqlite3
from typing import Any
from .db import Database
from .fulfillment import in_delivery_hours, extra_fee, pickup_restriction

class Problem(Exception):
 def __init__(self,status:int,code:str,message:str):
  self.status,self.code,self.message=status,code,message
  super().__init__(message)

def fail(status,code,message):raise Problem(status,code,message)
def dump(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(value):return hashlib.sha256(dump(value).encode()).hexdigest()
def row(c,sql,args=()):
 r=c.execute(sql,args).fetchone()
 if r is None:fail(404,'not_found','记录不存在')
 return dict(r)
def rows(c,sql,args=()):return [dict(r) for r in c.execute(sql,args)]
def identifier(prefix):return prefix+'_'+secrets.token_hex(8)

def distance_km(a,b,x,y):
 p1,p2=math.radians(a),math.radians(x)
 v=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(y-b)/2)**2
 return 6371.0088*2*math.asin(min(1,math.sqrt(v)))

class Retail:
 def __init__(self,db:Database):self.db=db
 def profile(self,c,store):
  r=c.execute('SELECT public_json FROM store_profile WHERE store_id=?',(store,)).fetchone()
  return json.loads(r['public_json']) if r else {}
 def review_issues(self,c,sku,store):
  r=c.execute('SELECT review_json FROM product_sources WHERE sku_id=?',(sku,)).fetchone()
  resolved={x['issue'] for x in c.execute('SELECT issue FROM review_resolutions WHERE store_id=? AND sku_id=?',(store,sku))}
  return [i for i in json.loads(r['review_json']) if i not in resolved] if r else []
 def check_review(self,c,sku,store):
  if self.review_issues(c,sku,store):fail(409,'review_required','该商品需要先核对导入异常，暂不可售')
 def audit(self,c,actor,action,entity,details=None,store=None):
  c.execute('INSERT INTO audit(actor_id,store_id,action,entity,detail_json,created) VALUES(?,?,?,?,?,?)',(actor.get('id') if actor else None,store or (actor or {}).get('store_id'),action,str(entity),dump(details or {}),self.db.clock()))
 def queue(self,c,kind,reference,payload):
  c.execute('INSERT OR IGNORE INTO outbox(kind,reference,payload_json,created) VALUES(?,?,?,?)',(kind,str(reference),dump(payload),self.db.clock()))
 def stock(self,c,store,sku,hand,reserved,reason,reference):
  changed=c.execute('UPDATE inventory SET on_hand=on_hand+?,reserved=reserved+? WHERE store_id=? AND sku_id=? AND on_hand+?>=0 AND reserved+?>=0 AND reserved+?<=on_hand+?',(hand,reserved,store,sku,hand,reserved,reserved,hand)).rowcount
  if changed!=1:fail(409,'stock_conflict','库存不足或库存已被其他订单预占')
  c.execute('INSERT INTO stock_ledger(store_id,sku_id,delta_hand,delta_reserved,reason,reference,created) VALUES(?,?,?,?,?,?,?)',(store,sku,hand,reserved,reason,str(reference),self.db.clock()))
 def staff_scope(self,actor,store,roles=('manager','picker')):
  if actor['role'] not in roles or actor['store_id']!=store:fail(403,'forbidden','无权操作此门店或此业务')
 def order_access(self,c,actor,oid):
  o=row(c,'SELECT * FROM orders WHERE id=?',(oid,))
  if actor['role']=='customer':
   if o['user_id']!=actor['id']:fail(404,'not_found','订单不存在')
  elif actor.get('store_id')!=o['store_id']:fail(404,'not_found','订单不存在')
  return o
 def _order(self,c,oid):
  o=row(c,'SELECT * FROM orders WHERE id=?',(oid,)); o['address']=json.loads(o.pop('address_json'))
  o['items']=rows(c,'SELECT * FROM order_lines WHERE order_id=? ORDER BY id',(oid,))
  shipping=c.execute('SELECT snapshot_json FROM order_shipping WHERE order_id=?',(oid,)).fetchone()
  o['shipping_detail']=json.loads(shipping['snapshot_json']) if shipping else None
  o['refunds']=rows(c,'SELECT * FROM refunds WHERE order_id=? ORDER BY created',(oid,))
  d=c.execute('SELECT * FROM deliveries WHERE order_id=?',(oid,)).fetchone();o['delivery']=dict(d) if d else None
  o['timeline']=rows(c,'SELECT action,detail_json,created FROM audit WHERE entity=? ORDER BY id',(oid,))
  for event in o['timeline']:event['detail']=json.loads(event.pop('detail_json'))
  o['net_paid_cents']=o['paid_cents']-o['refunded_cents']
  return o
 def order(self,actor,oid):
  with self.db.tx() as c:
   self.expire(c); self.order_access(c,actor,oid);return self._order(c,oid)
 def list_orders(self,actor):
  with self.db.tx() as c:
   self.expire(c)
   if actor['role']=='customer': ids=c.execute('SELECT id FROM orders WHERE user_id=? ORDER BY created DESC,id DESC',(actor['id'],)).fetchall()
   else:ids=c.execute('SELECT id FROM orders WHERE store_id=? ORDER BY created DESC,id DESC',(actor['store_id'],)).fetchall()
   return [self._order(c,i['id']) for i in ids]
 def catalog(self,store=1,q='',category=None,page=None,page_size=24):
  with self.db.read() as c:
   params=[store]; where=' WHERE i.store_id=?'
   if q:
    where+=' AND (p.name LIKE ? ESCAPE \'!\' OR p.barcode LIKE ? ESCAPE \'!\' OR CAST(p.id AS TEXT) LIKE ? ESCAPE \'!\')'
    term='%'+q.replace('!','!!').replace('%','!%').replace('_','!_')+'%';params.extend([term,term,term])
   if category:where+=' AND p.category_id=?';params.append(category)
   sql="SELECT p.*,i.store_id,i.price_cents,i.old_price_cents,i.on_hand,i.reserved,i.active,i.version,i.on_hand-i.reserved available,f.weight_g,COALESCE(f.pickup_only,0) pickup_only,COALESCE(f.reason,'') fulfillment_note FROM products p JOIN inventory i ON i.sku_id=p.id LEFT JOIN product_fulfillment f ON f.store_id=i.store_id AND f.sku_id=p.id"+where+' ORDER BY p.id'
   if page is None:return rows(c,sql,params)
   total=c.execute('SELECT COUNT(*) FROM products p JOIN inventory i ON i.sku_id=p.id'+where,params).fetchone()[0]
   pages=max(1,math.ceil(total/page_size));page=max(1,min(page,pages))
   items=rows(c,sql+' LIMIT ? OFFSET ?',params+[page_size,(page-1)*page_size])
   return {'items':items,'total':total,'page':page,'pages':pages,'page_size':page_size}
 def cart(self,actor,store=1):
  with self.db.read() as c:
   items=rows(c,"SELECT p.*,i.price_cents,i.old_price_cents,i.on_hand-i.reserved available,i.active,t.quantity,t.selected,f.weight_g,COALESCE(f.pickup_only,0) pickup_only,COALESCE(f.reason,'') fulfillment_note FROM cart t JOIN products p ON p.id=t.sku_id JOIN inventory i ON i.sku_id=t.sku_id AND i.store_id=t.store_id LEFT JOIN product_fulfillment f ON f.store_id=i.store_id AND f.sku_id=p.id WHERE t.user_id=? AND t.store_id=? ORDER BY p.id",(actor['id'],store))
   for item in items:item['valid']=bool(item['active'] and item['available']>=item['quantity'])
   return {'items':items,'count':sum(x['quantity'] for x in items),'subtotal_cents':sum(x['price_cents']*x['quantity'] for x in items if x['selected'] and x['active'] and x['available']>=x['quantity'])}
 def set_cart(self,actor,sku,quantity,selected=True,store=1):
  with self.db.tx() as c:
   p=row(c,'SELECT * FROM inventory WHERE sku_id=? AND store_id=?',(sku,store))
   if quantity:
    self.check_review(c,sku,store)
    if not p['active']:fail(409,'inactive','商品已下架')
    if quantity>p['on_hand']-p['reserved']:fail(409,'sold_out','该规格库存不足')
    c.execute('INSERT INTO cart VALUES(?,?,?,?,?) ON CONFLICT(user_id,store_id,sku_id) DO UPDATE SET quantity=excluded.quantity,selected=excluded.selected',(actor['id'],store,sku,quantity,int(selected)))
   else:c.execute('DELETE FROM cart WHERE user_id=? AND store_id=? AND sku_id=?',(actor['id'],store,sku))
  return self.cart(actor,store)
 def _calculate(self,c,actor,data):
  store=row(c,'SELECT * FROM stores WHERE id=?',(data['store_id'],))
  if not store['open']:fail(409,'closed','门店已打烊，暂时不能下单')
  profile=self.profile(c,store['id'])
  if profile:
   from datetime import datetime, timezone, timedelta
   hour=datetime.fromtimestamp(self.db.clock(),timezone(timedelta(hours=8))).hour
   if not 6<=hour<23:fail(409,'closed','营业时间为06:00–23:00')
  rules=profile.get('delivery_rules')
  if rules and data['method']=='delivery' and not in_delivery_hours(self.db.clock(),rules):
   fail(422,'delivery_hours',f'配送下单时间暂定为{rules["start"]}–{rules["end"]}，其他时段可到店自提')
  items=[]; subtotal=0; weight=0; weight_complete=True
  for item in sorted(data['items'],key=lambda i:i['sku_id']):
   p=row(c,"SELECT p.*,i.price_cents,i.version,i.active,i.on_hand-i.reserved available,f.weight_g,COALESCE(f.pickup_only,0) pickup_only,COALESCE(f.reason,'') fulfillment_note FROM products p JOIN inventory i ON i.sku_id=p.id LEFT JOIN product_fulfillment f ON f.store_id=i.store_id AND f.sku_id=p.id WHERE i.store_id=? AND p.id=?",(store['id'],item['sku_id']))
   if data['method']=='delivery' and p['pickup_only']:fail(422,'pickup_only',p['name']+'仅限到店自提，请切换自提或移除该商品')
   self.check_review(c,item['sku_id'],store['id'])
   if not p['active']:fail(409,'inactive',p['name']+'已下架')
   if p['available']<item['quantity']:fail(409,'sold_out',p['name']+'库存不足')
   if p['weight_g'] is None:
    weight_complete=False
    if rules and data['method']=='delivery':fail(422,'weight_required',p['name']+'尚未设置配送计费重量，请联系门店或选择自提')
   else:weight+=p['weight_g']*item['quantity']
   amount=p['price_cents']*item['quantity'];subtotal+=amount
   items.append({'sku_id':p['id'],'name':p['name'],'unit':p['unit'],'image':p['image'],'quantity':item['quantity'],'price_cents':p['price_cents'],'version':p['version'],'gross_cents':amount,'weight_g':p['weight_g'],'pickup_only':bool(p['pickup_only'])})
  address={}; shipping=0; distance=0
  if data['method']=='delivery':
   if profile and not profile.get('delivery_confirmed'):fail(422,'delivery_unconfirmed','园区配送边界尚未确认，请先选择到店自提')
   if not data.get('address_id'):fail(422,'address_required','请选择收货地址')
   address=row(c,'SELECT * FROM addresses WHERE id=? AND user_id=?',(data['address_id'],actor['id']))
   distance=distance_km(store['latitude'],store['longitude'],address['latitude'],address['longitude'])
   if distance>store['radius_km']:fail(422,'out_of_range','该地址超出配送范围，请选择到店自提')
   if subtotal<store['minimum_cents']:fail(422,'minimum_order',f'配送订单需满{store["minimum_cents"]/100:.2f}元')
  discount=0;coupon_id=data.get('coupon_id')
  if coupon_id:
   coupon=row(c,'SELECT * FROM coupons WHERE id=? AND user_id=?',(coupon_id,actor['id']))
   if coupon['state']!='available' or coupon['expires']<=self.db.clock():fail(409,'coupon_unavailable','优惠券已占用、已使用或已过期')
   if subtotal<coupon['minimum_cents']:fail(422,'coupon_minimum','未达到优惠券使用门槛')
   discount=min(coupon['discount_cents'],subtotal-1)
  # Free delivery is based on merchandise AFTER discount; this policy is explicit in both clients.
  if data['method']=='delivery' and subtotal-discount<store['free_shipping_cents']:shipping=store['delivery_cents']
  base_shipping=shipping
  surcharge=extra_fee(weight,rules) if rules and data['method']=='delivery' else 0
  shipping+=surcharge
  shipping_detail={'weight_g':weight if weight_complete else None,'base_cents':base_shipping,'extra_weight_cents':surcharge,'rules':rules,'total_cents':shipping}
  allocated=0
  for item in items:
   item['discount_cents']=discount*item['gross_cents']//subtotal;allocated+=item['discount_cents']
  ranking=sorted(range(len(items)),key=lambda n:(-(discount*items[n]['gross_cents']%subtotal),items[n]['sku_id']))
  for n in ranking[:discount-allocated]:items[n]['discount_cents']+=1
  for item in items:item['net_cents']=item['gross_cents']-item['discount_cents']
  return {'store_id':store['id'],'store_version':store['version'],'method':data['method'],'items':items,'address':address,'distance_km':round(distance,2),'subtotal_cents':subtotal,'discount_cents':discount,'shipping_cents':shipping,'shipping_detail':shipping_detail,'total_cents':subtotal-discount+shipping,'coupon_id':coupon_id}
 def quote(self,actor,data):
  with self.db.tx() as c:
   self.expire(c); snapshot=self._calculate(c,actor,data)
   qid=identifier('q');exp=self.db.clock()+120
   c.execute('INSERT INTO quotes VALUES(?,?,?,?,?,?)',(qid,actor['id'],dump(data),dump(snapshot),digest(snapshot),exp))
   return {'id':qid,'expires':exp,**snapshot}
 def create_order(self,actor,quote_id,key):
  with self.db.tx() as c:
   prior=c.execute('SELECT * FROM idempotency WHERE user_id=? AND scope=? AND key=?',(actor['id'],'order',key)).fetchone()
   if prior:
    if prior['fingerprint']!=digest(quote_id):fail(409,'key_conflict','同一幂等键不能用于不同请求')
    return self._order(c,prior['result_id'])
   self.expire(c)
   q=row(c,'SELECT * FROM quotes WHERE id=? AND user_id=?',(quote_id,actor['id']))
   if q['expires']<=self.db.clock():fail(409,'quote_expired','报价已过期，请重新结算')
   if c.execute('SELECT 1 FROM orders WHERE quote_id=?',(quote_id,)).fetchone():fail(409,'quote_used','该报价已生成订单')
   snap=self._calculate(c,actor,json.loads(q['request_json']))
   if digest(snap)!=q['fingerprint']:fail(409,'quote_changed','商品价格、地址或门店规则发生变化，请重新结算')
   oid=identifier('JM');now=self.db.clock();code=f'{secrets.randbelow(1000000):06d}'
   c.execute('INSERT INTO orders(id,number,user_id,store_id,quote_id,state,method,address_json,subtotal_cents,discount_cents,shipping_cents,total_cents,coupon_id,pickup_code,created,expires) VALUES(?,?,?,?,?,\'pending_payment\',?,?,?,?,?,?,?,?,?,?)',(oid,'JM'+str(int(now))[-6:]+secrets.token_hex(3).upper(),actor['id'],snap['store_id'],quote_id,snap['method'],dump(snap['address']),snap['subtotal_cents'],snap['discount_cents'],snap['shipping_cents'],snap['total_cents'],snap['coupon_id'],code,now,now+900))
   c.execute('INSERT INTO order_shipping VALUES(?,?)',(oid,dump(snap['shipping_detail'])))
   for item in snap['items']:
    self.stock(c,snap['store_id'],item['sku_id'],0,item['quantity'],'reserve',oid)
    c.execute('INSERT INTO order_lines(order_id,sku_id,name,unit,image,quantity,price_cents,discount_cents,net_cents) VALUES(?,?,?,?,?,?,?,?,?)',(oid,item['sku_id'],item['name'],item['unit'],item['image'],item['quantity'],item['price_cents'],item['discount_cents'],item['net_cents']))
    current=c.execute('SELECT quantity FROM cart WHERE user_id=? AND store_id=? AND sku_id=?',(actor['id'],snap['store_id'],item['sku_id'])).fetchone()
    if current:
     remain=current['quantity']-item['quantity']
     if remain>0:c.execute('UPDATE cart SET quantity=? WHERE user_id=? AND store_id=? AND sku_id=?',(remain,actor['id'],snap['store_id'],item['sku_id']))
     else:c.execute('DELETE FROM cart WHERE user_id=? AND store_id=? AND sku_id=?',(actor['id'],snap['store_id'],item['sku_id']))
   if snap['coupon_id']:c.execute('UPDATE coupons SET state=\'reserved\',order_id=? WHERE id=?',(oid,snap['coupon_id']))
   c.execute('INSERT INTO idempotency VALUES(?,?,?,?,?)',(actor['id'],'order',key,digest(quote_id),oid))
   self.audit(c,actor,'order.created',oid,{'total_cents':snap['total_cents']},snap['store_id'])
   return self._order(c,oid)
 def _cancel_unpaid(self,c,o,reason):
  for line in rows(c,'SELECT * FROM order_lines WHERE order_id=?',(o['id'],)):
   self.stock(c,o['store_id'],line['sku_id'],0,-line['quantity'],'release',o['id'])
  c.execute('UPDATE orders SET state=\'cancelled\',version=version+1 WHERE id=?',(o['id'],))
  c.execute('UPDATE coupons SET state=\'available\',order_id=NULL WHERE order_id=? AND state=\'reserved\'',(o['id'],))
  self.audit(c,None,'order.'+reason,o['id'],store=o['store_id'])
 def expire(self,c=None):
  if c is None:
   with self.db.tx() as conn:return self.expire(conn)
  expired=rows(c,'SELECT * FROM orders WHERE state=\'pending_payment\' AND expires<=?',(self.db.clock(),))
  for o in expired:self._cancel_unpaid(c,o,'expired')
  return len(expired)
 def gateway_charge(self,actor,oid,success=True):
  with self.db.tx() as c:
   self.expire(c);o=self.order_access(c,actor,oid)
   old=c.execute('SELECT * FROM gateway_ledger WHERE kind=\'charge\' AND reference=?',(oid,)).fetchone()
   if not old:
    if o['state']!='pending_payment':fail(409,'bad_state','当前订单不可付款')
    if not success:fail(402,'payment_declined','模拟支付失败，未产生任何扣款')
    c.execute('INSERT INTO gateway_ledger(kind,reference,order_id,amount_cents,created) VALUES(\'charge\',?,?,?,?)',(oid,oid,o['total_cents'],self.db.clock()))
   return {'event_id':identifier('evt'),'timestamp':int(self.db.clock()),'order_id':oid,'amount_cents':o['total_cents'],'currency':'CNY','transaction_id':'mock-pay-'+oid,'status':'success'}
 def _refund(self,c,o,amount,kind,reason,line=None,quantity=0,state='pending'):
  pending=c.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE order_id=? AND state IN(\'requested\',\'pending\',\'failed\')',(o['id'],)).fetchone()[0]
  if amount<=0 or amount+pending+o['refunded_cents']>o['paid_cents']:fail(409,'refund_limit','可退款余额不足或已有退款处理中')
  rid=identifier('RF')
  c.execute('INSERT INTO refunds(id,order_id,line_id,amount_cents,quantity,kind,reason,state,created) VALUES(?,?,?,?,?,?,?,?,?)',(rid,o['id'],line,amount,quantity,kind,reason,state,self.db.clock()))
  if state=='pending':self.queue(c,'refund',rid,{'refund_id':rid})
  return rid
 def payment_event(self,event):
  with self.db.tx() as c:
   old=c.execute('SELECT * FROM webhook_receipts WHERE channel=\'payment\' AND event_id=?',(event['event_id'],)).fetchone()
   if old:
    if old['payload_hash']!=digest(event):fail(409,'event_conflict','同一事件ID的数据不一致')
    return {'accepted':True,'duplicate':True}
   # Reject malformed/foreign-provider transactions BEFORE writing a successful payment.
   o=row(c,'SELECT * FROM orders WHERE id=?',(event['order_id'],))
   if event['currency']!='CNY' or event['amount_cents']!=o['total_cents'] or event['status']!='success' or event['transaction_id']!='mock-pay-'+o['id']:
    fail(422,'payment_mismatch','支付币种、金额、状态或交易号不匹配')
   self.expire(c);o=row(c,'SELECT * FROM orders WHERE id=?',(o['id'],))
   provider=row(c,'SELECT * FROM gateway_ledger WHERE kind=\'charge\' AND reference=?',(o['id'],))
   if provider['amount_cents']!=event['amount_cents']:fail(422,'provider_mismatch','支付网关账单不匹配')
   duplicate=bool(o['paid_cents'])
   if not duplicate:
    c.execute('UPDATE orders SET paid_cents=?,paid_at=?,version=version+1 WHERE id=?',(o['total_cents'],self.db.clock(),o['id']))
    if o['state']=='cancelled':
     o['paid_cents']=o['total_cents'];self._refund(c,o,o['total_cents'],'late_payment','超时后到账，自动原路退款')
     c.execute('UPDATE orders SET state=\'refund_pending\' WHERE id=?',(o['id'],))
     self.audit(c,None,'payment.late_refund',o['id'],store=o['store_id'])
    elif o['state']=='pending_payment':
     for line in rows(c,'SELECT * FROM order_lines WHERE order_id=?',(o['id'],)):
      self.stock(c,o['store_id'],line['sku_id'],-line['quantity'],-line['quantity'],'sale',o['id'])
     c.execute('UPDATE orders SET state=\'paid\' WHERE id=?',(o['id'],))
     c.execute('UPDATE coupons SET state=\'used\' WHERE order_id=?',(o['id'],))
     self.queue(c,'print',o['id'],{'order_id':o['id']})
     self.queue(c,'notify','paid:'+o['id'],{'user_id':o['user_id'],'message':'付款成功，门店正在为你准备新鲜好物。'})
     self.audit(c,None,'payment.succeeded',o['id'],{'amount_cents':o['total_cents']},o['store_id'])
    else:fail(409,'bad_state','订单状态不允许确认付款')
   c.execute('INSERT INTO webhook_receipts VALUES(\'payment\',?,?,?)',(event['event_id'],digest(event),self.db.clock()))
   return {'accepted':True,'duplicate':duplicate}
 def cancel(self,actor,oid):
  with self.db.tx() as c:
   self.expire(c);o=self.order_access(c,actor,oid)
   if actor['role']!='customer':self.staff_scope(actor,o['store_id'],('manager',))
   if o['state'] in ('cancelled','refunded','refund_pending'):return self._order(c,oid)
   if o['state']=='pending_payment':self._cancel_unpaid(c,o,'cancelled')
   else:
    local=bool(self.profile(c,o['store_id']))
    if actor['role']=='customer' and not local:fail(409,'contact_store','付款后请联系门店取消订单')
    if actor['role']!='customer':self.staff_scope(actor,o['store_id'],('manager',))
    if o['state'] not in (('paid','picking','ready','delivering') if local else ('paid','picking','ready')):fail(409,'bad_state','已完成订单请走售后流程')
    dispatched=o['state']=='delivering'
    pending=c.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE order_id=? AND state IN(\'requested\',\'pending\',\'failed\')',(oid,)).fetchone()[0]
    remaining=o['paid_cents']-o['refunded_cents']-pending
    retained=min(200,remaining) if dispatched else 0
    amount=remaining-retained
    if amount:self._refund(c,o,amount,'cancel','取消订单，配送开始后扣2元配送费' if dispatched else '取消订单')
    for line in rows(c,'SELECT * FROM order_lines WHERE order_id=?',(oid,)):
     qty=line['quantity']-line['shortage_qty']
     if qty and not dispatched:self.stock(c,o['store_id'],line['sku_id'],qty,0,'cancel_return',oid)
    c.execute('UPDATE orders SET state=?,version=version+1 WHERE id=?',('refund_pending' if amount or pending else 'cancelled',oid))
    c.execute("UPDATE deliveries SET state='cancelled' WHERE order_id=? AND state IN('created','accepted','picked_up')",(oid,))
    self.audit(c,actor,'order.cancel_refund',oid,{'retained_delivery_cents':retained,'return_stock_pending':dispatched},o['store_id'])
   return self._order(c,oid)
 def accept(self,actor,oid):
  with self.db.tx() as c:
   o=self.order_access(c,actor,oid);self.staff_scope(actor,o['store_id'])
   if o['state']=='picking':return self._order(c,oid)
   if o['state']!='paid':fail(409,'bad_state','仅已付款订单可以接单')
   c.execute('UPDATE orders SET state=\'picking\',version=version+1 WHERE id=?',(oid,));self.audit(c,actor,'order.accepted',oid)
   return self._order(c,oid)
 def pick(self,actor,oid,line_id,quantity):
  with self.db.tx() as c:
   o=self.order_access(c,actor,oid);self.staff_scope(actor,o['store_id'])
   if o['state']!='picking':fail(409,'bad_state','订单不在拣货状态')
   line=row(c,'SELECT * FROM order_lines WHERE id=? AND order_id=?',(line_id,oid))
   if quantity>line['quantity']-line['shortage_qty']:fail(422,'pick_limit','拣货数量超过可履约数量')
   c.execute('UPDATE order_lines SET picked_qty=? WHERE id=?',(quantity,line_id));self.audit(c,actor,'order.picked',oid,{'line_id':line_id,'quantity':quantity})
   return self._order(c,oid)
 def shortage(self,actor,oid,line_id,quantity,key):
  with self.db.tx() as c:
   o=self.order_access(c,actor,oid);self.staff_scope(actor,o['store_id'])
   scope='shortage:'+oid;fingerprint=digest([line_id,quantity])
   prior=c.execute('SELECT * FROM idempotency WHERE user_id=? AND scope=? AND key=?',(actor['id'],scope,key)).fetchone()
   if prior:
    if prior['fingerprint']!=fingerprint:fail(409,'key_conflict','同一幂等键不能用于不同缺货操作')
    return self._order(c,oid)
   if o['state']!='picking':fail(409,'bad_state','只有拣货中的订单可登记缺货')
   line=row(c,'SELECT * FROM order_lines WHERE id=? AND order_id=?',(line_id,oid));total=line['shortage_qty']+quantity
   if total+line['picked_qty']>line['quantity']:fail(422,'shortage_limit','缺货数量超过未拣货数量')
   amount=line['net_cents']*total//line['quantity']-line['net_cents']*line['shortage_qty']//line['quantity']
   c.execute('UPDATE order_lines SET shortage_qty=? WHERE id=?',(total,line_id))
   remain=c.execute('SELECT SUM(quantity-shortage_qty) FROM order_lines WHERE order_id=?',(oid,)).fetchone()[0]
   if remain==0:amount+=o['shipping_cents'];c.execute('UPDATE orders SET state=\'refund_pending\' WHERE id=?',(oid,))
   if amount:self._refund(c,o,amount,'shortage','拣货缺货退款（不回补不存在的实物）',line_id,quantity)
   c.execute('INSERT INTO idempotency VALUES(?,?,?,?,?)',(actor['id'],scope,key,fingerprint,oid))
   self.audit(c,actor,'order.shortage',oid,{'line_id':line_id,'quantity':quantity,'refund_cents':amount})
   return self._order(c,oid)
 def ready(self,actor,oid):
  with self.db.tx() as c:
   o=self.order_access(c,actor,oid);self.staff_scope(actor,o['store_id'])
   if o['state']=='ready':return self._order(c,oid)
   if o['state']!='picking':fail(409,'bad_state','请先接单并完成拣货')
   lines=rows(c,'SELECT * FROM order_lines WHERE order_id=?',(oid,))
   if any(l['picked_qty']+l['shortage_qty']!=l['quantity'] for l in lines):fail(409,'not_picked','还有商品尚未拣货或登记缺货')
   c.execute('UPDATE orders SET state=\'ready\',version=version+1 WHERE id=?',(oid,));self.audit(c,actor,'order.ready',oid)
   self.queue(c,'notify','ready:'+oid,{'user_id':o['user_id'],'message':'商品已打包，可到店自提。' if o['method']=='pickup' else '商品已打包，等待配送。'})
   return self._order(c,oid)
 def verify_pickup(self,actor,oid,code):
  with self.db.tx() as c:
   o=self.order_access(c,actor,oid);self.staff_scope(actor,o['store_id'])
   if o['method']!='pickup':fail(409,'not_pickup','这不是到店自提订单')
   if not secrets.compare_digest(o['pickup_code'],code):fail(422,'bad_pickup_code','核销码不正确')
   if o['state']=='completed':return self._order(c,oid)
   if o['state']!='ready':fail(409,'bad_state','请先完成打包')
   c.execute('UPDATE orders SET state=\'completed\',completed_at=?,version=version+1 WHERE id=?',(self.db.clock(),oid));self.audit(c,actor,'order.pickup_completed',oid)
   return self._order(c,oid)
 def dispatch(self,actor,oid):
  with self.db.tx() as c:
   o=self.order_access(c,actor,oid);self.staff_scope(actor,o['store_id'])
   old=c.execute('SELECT * FROM deliveries WHERE order_id=?',(oid,)).fetchone()
   if old:return dict(old)
   if o['state']!='ready' or o['method']!='delivery':fail(409,'bad_state','只有已打包的配送订单可以呼叫骑手')
   if row(c,'SELECT * FROM switches WHERE key=\'delivery_unavailable\'')['value']:fail(503,'delivery_unavailable','模拟配送平台暂不可用，请重试；订单仍然保留')
   did=identifier('DL');store=row(c,'SELECT * FROM stores WHERE id=?',(o['store_id'],))
   courier='商家自配送 · 本地演练' if self.profile(c,o['store_id']) else '阿青 · 模拟骑手'
   c.execute('INSERT INTO deliveries VALUES(?,?,\'created\',?,?,?,?)',(did,oid,courier,store['latitude'],store['longitude'],self.db.clock()))
   self.audit(c,actor,'delivery.created',oid,{'delivery_id':did});return row(c,'SELECT * FROM deliveries WHERE id=?',(did,))
 def delivery_event(self,event):
  with self.db.tx() as c:
   old=c.execute('SELECT * FROM webhook_receipts WHERE channel=\'delivery\' AND event_id=?',(event['event_id'],)).fetchone()
   if old:
    if old['payload_hash']!=digest(event):fail(409,'event_conflict','同一事件ID的数据不一致')
    return {'accepted':True,'duplicate':True}
   d=row(c,'SELECT * FROM deliveries WHERE id=?',(event['delivery_id'],));o=row(c,'SELECT * FROM orders WHERE id=?',(d['order_id'],))
   next_state={'created':'accepted','accepted':'picked_up','picked_up':'delivered'}
   duplicate=event['status']==d['state']
   if not duplicate:
    if next_state.get(d['state'])!=event['status']:fail(409,'delivery_state','配送事件乱序或状态不合法')
    c.execute('UPDATE deliveries SET state=?,latitude=?,longitude=? WHERE id=?',(event['status'],event.get('latitude',d['latitude']),event.get('longitude',d['longitude']),d['id']))
    if event['status']=='picked_up':c.execute('UPDATE orders SET state=\'delivering\',version=version+1 WHERE id=?',(o['id'],))
    if event['status']=='delivered':c.execute('UPDATE orders SET state=\'completed\',completed_at=?,version=version+1 WHERE id=?',(self.db.clock(),o['id']))
    self.audit(c,None,'delivery.'+event['status'],o['id'],store=o['store_id'])
   c.execute('INSERT INTO webhook_receipts VALUES(\'delivery\',?,?,?)',(event['event_id'],digest(event),self.db.clock()))
   return {'accepted':True,'duplicate':duplicate}
 def request_aftersale(self,actor,oid,reason,key):
  with self.db.tx() as c:
   o=self.order_access(c,actor,oid)
   prior=c.execute('SELECT * FROM idempotency WHERE user_id=? AND scope=? AND key=?',(actor['id'],'aftersale',key)).fetchone()
   fp=digest([oid,reason])
   if prior:
    if fp!=prior['fingerprint']:fail(409,'key_conflict','同一幂等键不能用于不同售后申请')
    return row(c,'SELECT * FROM refunds WHERE id=?',(prior['result_id'],))
   if o['state']!='completed':fail(409,'bad_state','完成订单后可申请售后；配送前请联系门店')
   rid=self._refund(c,o,o['paid_cents']-o['refunded_cents'],'after_sale',reason,state='requested')
   c.execute('INSERT INTO idempotency VALUES(?,?,?,?,?)',(actor['id'],'aftersale',key,fp,rid));self.audit(c,actor,'refund.requested',oid,{'refund_id':rid},o['store_id'])
   return row(c,'SELECT * FROM refunds WHERE id=?',(rid,))
 def approve_refund(self,actor,rid,approve=True):
  with self.db.tx() as c:
   r=row(c,'SELECT * FROM refunds WHERE id=?',(rid,));o=self.order_access(c,actor,r['order_id']);self.staff_scope(actor,o['store_id'],('manager',))
   if r['state']!='requested':fail(409,'bad_state','该申请已处理')
   c.execute('UPDATE refunds SET state=? WHERE id=?',('pending' if approve else 'rejected',rid))
   if approve:self.queue(c,'refund',rid,{'refund_id':rid})
   self.audit(c,actor,'refund.approved' if approve else 'refund.rejected',o['id'],{'refund_id':rid})
   return row(c,'SELECT * FROM refunds WHERE id=?',(rid,))
 def drain(self):
  with self.db.tx() as c:
   self.expire(c);jobs=rows(c,'SELECT * FROM outbox WHERE state!=\'done\' ORDER BY id LIMIT 500');done=0
   switches={r['key']:r['value'] for r in c.execute('SELECT * FROM switches')}
   for job in jobs:
    c.execute('UPDATE outbox SET attempts=attempts+1 WHERE id=?',(job['id'],));payload=json.loads(job['payload_json']);error=None
    if job['kind']=='print':
     if switches['printer_offline']:error='模拟打印机离线，可恢复后重试'
     else:
      o=self._order(c,payload['order_id']);text=f'京漫便民 · 模拟小票\n{o["number"]}\n'+ '\n'.join(f'{i["name"]} {i["unit"]} ×{i["quantity"]}' for i in o['items'])+f'\n实付 ¥{o["total_cents"]/100:.2f}'
      c.execute('INSERT OR IGNORE INTO print_receipts(order_id,body,created) VALUES(?,?,?)',(o['id'],text,self.db.clock()))
    elif job['kind']=='notify':
     c.execute('INSERT OR IGNORE INTO notifications(user_id,reference,message,created) VALUES(?,?,?,?)',(payload['user_id'],job['reference'],payload['message'],self.db.clock()))
    elif job['kind']=='refund':
     r=row(c,'SELECT * FROM refunds WHERE id=?',(payload['refund_id'],))
     if r['state']=='succeeded':pass
     elif switches['refund_failure']:
      error='模拟退款网关超时，退款金额尚未到账';c.execute('UPDATE refunds SET state=\'failed\' WHERE id=?',(r['id'],))
     else:
      o=row(c,'SELECT * FROM orders WHERE id=?',(r['order_id'],))
      c.execute('INSERT OR IGNORE INTO gateway_ledger(kind,reference,order_id,amount_cents,created) VALUES(\'refund\',?,?,?,?)',(r['id'],o['id'],r['amount_cents'],self.db.clock()))
      c.execute('UPDATE refunds SET state=\'succeeded\',completed=? WHERE id=?',(self.db.clock(),r['id']))
      c.execute('UPDATE orders SET refunded_cents=refunded_cents+?,version=version+1 WHERE id=?',(r['amount_cents'],o['id']))
      if o['refunded_cents']+r['amount_cents']==o['paid_cents']:c.execute('UPDATE orders SET state=\'refunded\' WHERE id=?',(o['id'],))
      elif o['state']=='refund_pending' and not c.execute("SELECT 1 FROM refunds WHERE order_id=? AND state IN('requested','pending','failed')",(o['id'],)).fetchone():
       c.execute("UPDATE orders SET state='cancelled' WHERE id=?",(o['id'],))
      self.audit(c,None,'refund.succeeded',o['id'],{'refund_id':r['id'],'amount_cents':r['amount_cents']},o['store_id'])
    if error:c.execute('UPDATE outbox SET state=\'failed\',error=? WHERE id=?',(error,job['id']))
    else:c.execute('UPDATE outbox SET state=\'done\',error=NULL WHERE id=?',(job['id'],));done+=1
   return {'processed':len(jobs),'done':done,'failed':len(jobs)-done}
 def adjust_inventory(self,actor,sku,delta,reason,key):
  store=actor['store_id'];self.staff_scope(actor,store,('manager',))
  fp=digest([sku,delta,reason])
  with self.db.tx() as c:
   prior=c.execute('SELECT * FROM idempotency WHERE user_id=? AND scope=\'inventory\' AND key=?',(actor['id'],key)).fetchone()
   if prior:
    if fp!=prior['fingerprint']:fail(409,'key_conflict','同一幂等键不能用于不同库存调整')
    return row(c,'SELECT * FROM inventory WHERE store_id=? AND sku_id=?',(store,sku))
   self.stock(c,store,sku,delta,0,reason,key)
   c.execute('INSERT INTO idempotency VALUES(?,\'inventory\',?,?,?)',(actor['id'],key,fp,str(sku)));self.audit(c,actor,'inventory.adjusted',sku,{'delta':delta,'reason':reason})
   return row(c,'SELECT * FROM inventory WHERE store_id=? AND sku_id=?',(store,sku))
 def edit_product(self,actor,sku,data):
  self.staff_scope(actor,actor['store_id'],('manager',))
  with self.db.tx() as c:
   p=row(c,'SELECT * FROM inventory WHERE store_id=? AND sku_id=?',(actor['store_id'],sku))
   if p['version']!=data['version']:fail(409,'version_conflict','商品已被修改，请刷新后重试')
   price=data.get('price_cents',p['price_cents']);active=int(data.get('active',p['active']))
   if active:self.check_review(c,sku,actor['store_id'])
   c.execute('UPDATE inventory SET price_cents=?,active=?,version=version+1 WHERE store_id=? AND sku_id=?',(price,active,actor['store_id'],sku))
   self.audit(c,actor,'product.updated',sku,{'price_cents':price,'active':active});return row(c,'SELECT * FROM inventory WHERE store_id=? AND sku_id=?',(actor['store_id'],sku))
 def edit_fulfillment(self,actor,sku,data):
  self.staff_scope(actor,actor['store_id'],('manager',))
  with self.db.tx() as c:
   p=row(c,'SELECT p.*,i.version,c.name category FROM products p JOIN inventory i ON i.sku_id=p.id JOIN categories c ON c.id=p.category_id WHERE p.id=? AND i.store_id=?',(sku,actor['store_id']))
   if p['version']!=data['version']:fail(409,'version_conflict','商品已被修改，请刷新后重试')
   old=c.execute('SELECT * FROM product_fulfillment WHERE store_id=? AND sku_id=?',(actor['store_id'],sku)).fetchone()
   previous=dict(old) if old else {'weight_g':None,'pickup_only':0,'reason':''}
   weight=data.get('weight_g',previous['weight_g']);pickup=data.get('pickup_only',bool(previous['pickup_only']))
   required=previous['reason'] or pickup_restriction(p['name'],p['category'].split(' / '))
   if required and not pickup:fail(422,'pickup_only_required','此商品已设置为仅限自提，不能开放配送')
   c.execute('INSERT INTO product_fulfillment VALUES(?,?,?,?,?) ON CONFLICT(store_id,sku_id) DO UPDATE SET weight_g=excluded.weight_g,pickup_only=excluded.pickup_only',(actor['store_id'],sku,weight,int(pickup),required))
   c.execute('UPDATE inventory SET version=version+1 WHERE store_id=? AND sku_id=?',(actor['store_id'],sku))
   self.audit(c,actor,'product.fulfillment_updated',sku,{'before':previous,'weight_g':weight,'pickup_only':pickup})
   return row(c,'SELECT f.*,i.version FROM product_fulfillment f JOIN inventory i ON i.store_id=f.store_id AND i.sku_id=f.sku_id WHERE f.store_id=? AND f.sku_id=?',(actor['store_id'],sku))
 def store_settings(self,actor,data):
  self.staff_scope(actor,actor['store_id'],('manager',))
  with self.db.tx() as c:
   store=row(c,'SELECT * FROM stores WHERE id=?',(actor['store_id'],))
   if data['version']!=store['version']:fail(409,'version_conflict','门店设置已变化，请刷新')
   for key in ('open','radius_km','minimum_cents','delivery_cents','free_shipping_cents'):
    if key in data:store[key]=data[key]
   c.execute('UPDATE stores SET open=?,radius_km=?,minimum_cents=?,delivery_cents=?,free_shipping_cents=?,version=version+1 WHERE id=?',(store['open'],store['radius_km'],store['minimum_cents'],store['delivery_cents'],store['free_shipping_cents'],store['id']))
   self.audit(c,actor,'store.updated',store['id'],data);return row(c,'SELECT * FROM stores WHERE id=?',(store['id'],))
 def delivery_rules(self,actor,data):
  self.staff_scope(actor,actor['store_id'],('manager',))
  with self.db.tx() as c:
   store=row(c,'SELECT * FROM stores WHERE id=?',(actor['store_id'],))
   if data['version']!=store['version']:fail(409,'version_conflict','门店规则已变化，请刷新')
   profile=self.profile(c,store['id'])
   if not profile.get('delivery_rules'):fail(422,'rules_unavailable','请先导入门店资料和配送规则')
   before=dict(profile['delivery_rules'])
   for key in ('start','end','rounding','provisional_hours','provisional_rounding'):profile['delivery_rules'][key]=data[key]
   c.execute('UPDATE store_profile SET public_json=? WHERE store_id=?',(dump(profile),store['id']))
   c.execute('UPDATE stores SET version=version+1 WHERE id=?',(store['id'],))
   self.audit(c,actor,'delivery.rules_updated',store['id'],{'before':before,'after':profile['delivery_rules']})
   return {'delivery_rules':profile['delivery_rules'],'version':store['version']+1}
 def reconciliation(self,actor):
  store=actor['store_id'];self.staff_scope(actor,store,('manager',));issues=[]
  with self.db.read() as c:
   for inv in rows(c,'SELECT * FROM inventory WHERE store_id=?',(store,)):
    balance=row(c,'SELECT COALESCE(SUM(delta_hand),0) hand,COALESCE(SUM(delta_reserved),0) reserved FROM stock_ledger WHERE store_id=? AND sku_id=?',(store,inv['sku_id']))
    expected=c.execute('SELECT COALESCE(SUM(l.quantity),0) FROM order_lines l JOIN orders o ON o.id=l.order_id WHERE o.store_id=? AND l.sku_id=? AND o.state=\'pending_payment\'',(store,inv['sku_id'])).fetchone()[0]
    if (inv['on_hand'],inv['reserved'])!=(balance['hand'],balance['reserved']) or inv['reserved']!=expected:issues.append({'type':'inventory','sku_id':inv['sku_id']})
   orders=rows(c,'SELECT * FROM orders WHERE store_id=?',(store,));waiting=[]
   for o in orders:
    charges=c.execute('SELECT COALESCE(SUM(amount_cents),0) FROM gateway_ledger WHERE kind=\'charge\' AND order_id=?',(o['id'],)).fetchone()[0]
    refunds=c.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE state=\'succeeded\' AND order_id=?',(o['id'],)).fetchone()[0]
    gateway_refunds=c.execute('SELECT COALESCE(SUM(amount_cents),0) FROM gateway_ledger WHERE kind=\'refund\' AND order_id=?',(o['id'],)).fetchone()[0]
    if charges and not o['paid_cents']:waiting.append(o['id'])
    elif charges!=o['paid_cents']:issues.append({'type':'payment','order_id':o['id']})
    if not(refunds==o['refunded_cents']==gateway_refunds):issues.append({'type':'refund','order_id':o['id']})
    sums=row(c,'SELECT SUM(net_cents) net,SUM(discount_cents) discount,SUM(quantity*price_cents) gross FROM order_lines WHERE order_id=?',(o['id'],))
    if sums['net']+o['shipping_cents']!=o['total_cents'] or sums['discount']!=o['discount_cents'] or sums['gross']!=o['subtotal_cents']:issues.append({'type':'allocation','order_id':o['id']})
   return {'ok':not issues and not waiting,'issues':issues,'awaiting_payment_callbacks':waiting,'checked_skus':c.execute('SELECT COUNT(*) FROM inventory WHERE store_id=?',(store,)).fetchone()[0],'checked_orders':len(orders),'paid_cents':sum(o['paid_cents'] for o in orders),'refunded_cents':sum(o['refunded_cents'] for o in orders),'net_cents':sum(o['paid_cents']-o['refunded_cents'] for o in orders),'checked_at':self.db.clock()}
 def dashboard(self,actor):
  self.staff_scope(actor,actor['store_id'],('manager','picker','rider'))
  with self.db.read() as c:
   orders=rows(c,'SELECT * FROM orders WHERE store_id=?',(actor['store_id'],))
   return {'order_count':len(orders),'paid_cents':sum(o['paid_cents'] for o in orders),'refund_cents':sum(o['refunded_cents'] for o in orders),'net_cents':sum(o['paid_cents']-o['refunded_cents'] for o in orders),'waiting':sum(o['state']=='paid' for o in orders),'picking':sum(o['state']=='picking' for o in orders),'completed':sum(o['state']=='completed' for o in orders),'low_stock':c.execute('SELECT COUNT(*) FROM inventory WHERE store_id=? AND on_hand-reserved<10',(actor['store_id'],)).fetchone()[0],'states':{s:sum(o['state']==s for o in orders) for s in ('pending_payment','paid','picking','ready','delivering','completed','cancelled','refunded')},'recent':rows(c,'SELECT action,entity,created,detail_json FROM audit WHERE store_id=? ORDER BY id DESC LIMIT 15',(actor['store_id'],))}
