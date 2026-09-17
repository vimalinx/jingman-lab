"""Acceptance scenarios: real HTTP handlers + real SQL, not canned-success mocks."""
from concurrent.futures import ThreadPoolExecutor
import json,sqlite3
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from conftest import KEY,SECRET

def test_lab_requires_explicit_opt_in(tmp_path):
 with pytest.raises(RuntimeError):create_app(tmp_path/'x.db',KEY,SECRET)
def test_lab_rejects_weak_secret(tmp_path):
 with pytest.raises(RuntimeError):create_app(tmp_path/'x.db','short','short',lab_enabled=True)
def test_authentication_required(h):
 assert h.c.get('/api/cart').status_code==401
 assert h.c.get('/api/admin/dashboard',headers={'Authorization':'Bearer fake'}).status_code==401
 assert h.c.get('/api/cart',headers={'X-User-Id':'1','X-Role':'manager'}).status_code==401

def test_bad_login_rate_limited(h):
 for _ in range(10):assert h.c.post('/api/session',json={'access_key':'wrong-but-long-key'}).status_code==401
 assert h.c.post('/api/session',json={'access_key':'wrong-but-long-key'}).status_code==429
 h.clock.advance(61)
 assert h.c.post('/api/session',json={'access_key':KEY}).status_code==200

def test_session_expiry_and_logout(h):
 assert h.request('DELETE','/api/session',who='customer')['ok']
 h.request('GET','/api/cart',status=401)
 h.clock.advance(13*3600)
 h.request('GET','/api/cart',who='customer2',status=401)

def test_session_tokens_not_stored_plaintext(h):
 values=h.sql('SELECT token_hash FROM sessions')
 assert len(values)==6 and all(len(v['token_hash'])==64 for v in values)
 assert all(v['token_hash'] not in h.headers['customer']['Authorization'] for v in values)

def test_catalog_search_variants_sold_out(h):
 assert len(h.request('GET','/api/products'))==16
 assert len(h.request('GET','/api/products?q=草莓'))==3
 assert len(h.request('GET','/api/products/103')['variants'])==3
 assert h.product(108)['available']==0
 assert h.request('GET',"/api/products?q=' OR 1=1 --")==[]
 assert h.request('GET','/api/products?q=%25')==[]

def test_cart_persists_and_isolates_users(h):
 h.request('PUT','/api/cart',{'sku_id':101,'quantity':2})
 assert h.request('GET','/api/cart')['subtotal_cents']==796
 assert h.request('GET','/api/cart',who='customer2')['items']==[]
 h.request('PUT','/api/cart',{'sku_id':101,'quantity':0})
 assert h.request('GET','/api/cart')['count']==0

@pytest.mark.parametrize('payload',[
 {'sku_id':101,'quantity':-1},{'sku_id':101,'quantity':100},{'sku_id':101,'quantity':1.5},
 {'sku_id':101,'quantity':'2'},{'sku_id':101,'quantity':True},{'sku_id':101,'quantity':1,'price_cents':1},
])
def test_cart_rejects_invalid_and_forged_fields(h,payload):h.request('PUT','/api/cart',payload,status=422)

def test_sold_out_cannot_be_added(h):h.request('PUT','/api/cart',{'sku_id':108,'quantity':1},status=409)
def test_price_tampering_rejected(h):
 h.request('POST','/api/quotes',{'items':[{'sku_id':101,'quantity':1,'price_cents':1}]},status=422)
 h.request('POST','/api/orders',{'quote_id':'q_not-real','total_cents':1},key='attack-1',status=422)
 h.request('POST','/api/quotes',{'items':[{'sku_id':101,'quantity':1},{'sku_id':101,'quantity':2}]},status=422)

def test_quote_is_server_priced_and_no_stock_reserved(h):
 q=h.quote();assert q['total_cents']==796 and h.product()['reserved']==0

def test_create_reserves_stock_and_uses_idempotency(h):
 q=h.quote();body={'quote_id':q['id']}
 a=h.request('POST','/api/orders',body,key='order-unique')
 b=h.request('POST','/api/orders',body,key='order-unique')
 assert a['id']==b['id'] and h.product()['reserved']==2 and len(h.sql('SELECT * FROM orders'))==1
 h.request('POST','/api/orders',body,key='another-key',status=409)
 other=h.quote();h.request('POST','/api/orders',{'quote_id':other['id']},key='order-unique',status=409)
 assert h.reconcile()['ok']

def test_idempotency_key_required(h):
 q=h.quote();h.request('POST','/api/orders',{'quote_id':q['id']},status=422)

def test_quote_expired_and_changed_price(h):
 q=h.quote();h.clock.advance(121)
 h.request('POST','/api/orders',{'quote_id':q['id']},key='expired-key',status=409)
 q=h.quote();p=h.product()
 h.request('PATCH','/api/admin/products/101',{'version':p['version'],'price_cents':499},who='manager')
 h.request('POST','/api/orders',{'quote_id':q['id']},key='changed-key',status=409)
 assert h.product()['reserved']==0

def test_quote_address_changed_requires_refresh(h):
 q=h.quote([{'sku_id':110,'quantity':1}],method='delivery',address_id=1)
 h.request('PUT','/api/addresses/1',{'name':'新收件人','mobile':'18800000001','address':'新地址 2号楼（虚构）','latitude':31.235,'longitude':121.48})
 h.request('POST','/api/orders',{'quote_id':q['id']},key='address-change',status=409)

def test_delivery_minimum_range_address_ownership(h):
 h.request('POST','/api/quotes',{'items':[{'sku_id':101,'quantity':1}],'method':'delivery','address_id':1},status=422)
 h.request('POST','/api/quotes',{'items':[{'sku_id':110,'quantity':1}],'method':'delivery','address_id':2},status=404)
 a=h.request('POST','/api/addresses',{'name':'远方顾客','mobile':'18800000001','address':'远方测试地址','latitude':32.23,'longitude':121.48})
 h.request('POST','/api/quotes',{'items':[{'sku_id':110,'quantity':1}],'method':'delivery','address_id':a['id']},status=422)
 assert h.quote([{'sku_id':101,'quantity':1}])['shipping_cents']==0

def test_free_shipping_uses_discounted_merchandise(h):
 q=h.quote([{'sku_id':103,'quantity':1},{'sku_id':113,'quantity':1}],method='delivery',address_id=1,coupon_id=1)
 assert q['subtotal_cents']==5280 and q['discount_cents']==300 and q['shipping_cents']==0
 q=h.quote([{'sku_id':110,'quantity':2},{'sku_id':101,'quantity':1}],method='delivery',address_id=1,coupon_id=1)
 assert q['subtotal_cents']==4954 and q['shipping_cents']==300

def test_coupon_allocation_has_no_penny_loss(h):
 q=h.quote([{'sku_id':101,'quantity':3},{'sku_id':102,'quantity':1},{'sku_id':103,'quantity':1}],coupon_id=1)
 assert sum(i['discount_cents'] for i in q['items'])==300
 assert sum(i['net_cents'] for i in q['items'])==q['total_cents']

def test_coupon_reservation_release_and_once_use(h):
 o=h.order([{'sku_id':110,'quantity':2}],coupon_id=1)
 assert h.request('GET','/api/coupons')[0]['state']=='reserved'
 h.request('POST','/api/quotes',{'items':[{'sku_id':110,'quantity':2}],'coupon_id':1},status=409)
 h.request('POST','/api/orders/'+o['id']+'/cancel',{})
 assert h.request('GET','/api/coupons')[0]['state']=='available'
 o=h.pay(h.order([{'sku_id':110,'quantity':2}],coupon_id=1))
 assert h.request('GET','/api/coupons')[0]['state']=='used' and h.reconcile()['ok']

def test_customer_cannot_use_other_customers_coupon(h):
 h.request('POST','/api/quotes',{'items':[{'sku_id':110,'quantity':2}],'coupon_id':4},status=404)

def test_cancel_and_expiry_release_exactly_once(h):
 o=h.order();h.request('POST','/api/orders/'+o['id']+'/cancel',{});h.request('POST','/api/orders/'+o['id']+'/cancel',{})
 assert h.product()['reserved']==0 and h.product()['on_hand']==48
 o=h.order();h.clock.advance(901);h.request('GET','/api/orders')
 assert h.product()['reserved']==0
 assert h.request('GET','/api/orders/'+o['id'])['state']=='cancelled'
 assert h.reconcile()['ok']

def test_pay_failure_does_not_deduct(h):
 o=h.order();h.request('POST','/api/lab/pay/'+o['id'],{'success':False},status=402)
 assert h.product()['on_hand']==48 and h.product()['reserved']==2
 assert h.sql('SELECT * FROM gateway_ledger')==[]
 assert h.request('GET','/api/orders/'+o['id'])['state']=='pending_payment'

def test_payment_callback_verified_and_idempotent(h):
 o=h.order();env=h.request('POST','/api/lab/gateway/charge/'+o['id'],{})
 assert not h.reconcile()['ok']
 e=env['event'];h.callback(e,signature='invalid',status=401)
 assert h.product()['on_hand']==48
 assert not h.callback(e)['duplicate']
 assert h.callback(e)['duplicate']
 assert h.product()['on_hand']==46 and h.product()['reserved']==0
 assert h.reconcile()['ok']

@pytest.mark.parametrize('field,value',[('amount_cents',1),('currency','USD'),('transaction_id','different'),('status','failure')])
def test_even_signed_mismatched_payment_is_rejected(h,field,value):
 o=h.order();e=h.request('POST','/api/lab/gateway/charge/'+o['id'],{})['event'];e[field]=value
 h.callback(e,status=422);assert h.product()['on_hand']==48

def test_webhook_window_and_event_payload_conflict(h):
 o=h.order();e=h.request('POST','/api/lab/gateway/charge/'+o['id'],{})['event']
 stale={**e,'timestamp':e['timestamp']-301};h.callback(stale,status=401)
 h.callback(e);h.callback({**e,'amount_cents':1},status=409)
 assert h.reconcile()['ok']

def test_late_payment_auto_refunds_without_restock_or_fulfillment(h):
 o=h.order();e=h.request('POST','/api/lab/gateway/charge/'+o['id'],{})['event']
 h.clock.advance(901);h.request('GET','/api/orders');e['timestamp']=int(h.clock())
 h.callback(e);state=h.request('GET','/api/orders/'+o['id']);assert state['state']=='refund_pending'
 h.worker();state=h.request('GET','/api/orders/'+o['id']);assert state['state']=='refunded'
 assert h.product()['on_hand']==48 and h.product()['reserved']==0
 assert h.sql('SELECT * FROM print_receipts')==[] and h.reconcile()['ok']

def test_pickup_full_lifecycle(h):
 o=h.pack(h.pay(h.order()))
 h.request('POST','/api/admin/orders/'+o['id']+'/pickup',{'code':'000000' if o['pickup_code']!='000000' else '111111'},who='picker',status=422)
 complete=h.request('POST','/api/admin/orders/'+o['id']+'/pickup',{'code':o['pickup_code']},who='picker')
 assert complete['state']=='completed'
 again=h.request('POST','/api/admin/orders/'+o['id']+'/pickup',{'code':o['pickup_code']},who='picker');assert again['state']=='completed'
 assert h.reconcile()['ok']

def test_cannot_skip_payment_and_picking(h):
 o=h.order();h.request('POST','/api/admin/orders/'+o['id']+'/accept',{},who='picker',status=409)
 o=h.accept(h.pay(o));h.request('POST','/api/admin/orders/'+o['id']+'/ready',{},who='picker',status=409)
 l=o['items'][0];h.request('POST','/api/admin/orders/'+o['id']+'/pick',{'line_id':l['id'],'quantity':l['quantity']+1},who='picker',status=422)

def test_shortage_partial_refund_and_print_failure_recovery(h):
 h.request('PUT','/api/lab/switch',{'key':'printer_offline','enabled':True},who='manager')
 h.request('PUT','/api/lab/switch',{'key':'refund_failure','enabled':True},who='manager')
 o=h.accept(h.pay(h.order([{'sku_id':101,'quantity':2},{'sku_id':110,'quantity':1}],coupon_id=1)))
 line=o['items'][0];body={'line_id':line['id'],'quantity':1};path='/api/admin/orders/'+o['id']+'/shortage'
 h.request('POST',path,body,who='picker',key='shortage-once');h.request('POST',path,body,who='picker',key='shortage-once')
 assert h.worker()['failed']==2
 current=h.request('GET','/api/orders/'+o['id']);assert current['refunded_cents']==0 and current['refunds'][0]['state']=='failed'
 h.request('PUT','/api/lab/switch',{'key':'printer_offline','enabled':False},who='manager')
 h.request('PUT','/api/lab/switch',{'key':'refund_failure','enabled':False},who='manager')
 assert h.worker()['failed']==0;h.worker()
 current=h.request('GET','/api/orders/'+o['id'])
 assert current['refunded_cents']==line['net_cents']//2
 assert len(h.sql('SELECT * FROM print_receipts'))==1
 assert len(h.sql("SELECT * FROM gateway_ledger WHERE kind='refund'"))==1
 assert h.product()['on_hand']==46 and h.reconcile()['ok']

def test_all_shortage_refunds_shipping_as_well(h):
 o=h.accept(h.pay(h.order([{'sku_id':110,'quantity':1}],method='delivery',address_id=1)))
 assert o['shipping_cents']==300
 h.request('POST','/api/admin/orders/'+o['id']+'/shortage',{'line_id':o['items'][0]['id'],'quantity':1},who='picker',key='all-shortage')
 h.worker();current=h.request('GET','/api/orders/'+o['id']);assert current['state']=='refunded' and current['refunded_cents']==o['total_cents']
 assert h.reconcile()['ok']

def test_shortage_cannot_refund_picked_items(h):
 o=h.accept(h.pay(h.order()));l=o['items'][0]
 h.request('POST','/api/admin/orders/'+o['id']+'/pick',{'line_id':l['id'],'quantity':2},who='picker')
 h.request('POST','/api/admin/orders/'+o['id']+'/shortage',{'line_id':l['id'],'quantity':1},who='picker',key='too-much-shortage',status=422)
 assert h.sql('SELECT * FROM refunds')==[]

def test_delivery_full_lifecycle_and_reordered_events(h):
 o=h.pack(h.pay(h.order([{'sku_id':110,'quantity':1}],method='delivery',address_id=1)))
 d=h.request('POST','/api/admin/orders/'+o['id']+'/dispatch',{},who='picker')
 assert h.request('POST','/api/admin/orders/'+o['id']+'/dispatch',{},who='picker')['id']==d['id']
 h.request('POST',f'/api/lab/delivery/{d["id"]}/delivered',{},who='rider',status=409)
 for s in ('accepted','picked_up','delivered'):h.request('POST',f'/api/lab/delivery/{d["id"]}/{s}',{},who='rider')
 assert h.request('GET','/api/orders/'+o['id'])['state']=='completed'
 assert h.request('GET','/api/rider/tasks',who='rider')[0]['mobile_masked']=='188****0001'
 assert h.reconcile()['ok']

def test_dispatch_outage_preserves_ready_order(h):
 o=h.pack(h.pay(h.order([{'sku_id':110,'quantity':1}],method='delivery',address_id=1)))
 h.request('PUT','/api/lab/switch',{'key':'delivery_unavailable','enabled':True},who='manager')
 h.request('POST','/api/admin/orders/'+o['id']+'/dispatch',{},who='picker',status=503)
 assert h.request('GET','/api/orders/'+o['id'])['state']=='ready'
 h.request('PUT','/api/lab/switch',{'key':'delivery_unavailable','enabled':False},who='manager')
 assert h.request('POST','/api/admin/orders/'+o['id']+'/dispatch',{},who='picker')['state']=='created'

def test_cancel_after_dispatch_does_not_resurrect_refunded_order(h):
 o=h.pack(h.pay(h.order([{'sku_id':110,'quantity':1}],method='delivery',address_id=1)))
 d=h.request('POST','/api/admin/orders/'+o['id']+'/dispatch',{},who='picker')
 h.request('POST','/api/orders/'+o['id']+'/cancel',{},who='manager');h.worker()
 h.request('POST',f'/api/lab/delivery/{d["id"]}/accepted',{},who='rider',status=409)
 assert h.request('GET','/api/orders/'+o['id'])['state']=='refunded' and h.reconcile()['ok']

def test_manager_cancel_paid_returns_real_stock_once(h):
 o=h.pay(h.order());h.request('POST','/api/orders/'+o['id']+'/cancel',{},status=409)
 h.request('POST','/api/orders/'+o['id']+'/cancel',{},who='manager');h.request('POST','/api/orders/'+o['id']+'/cancel',{},who='manager');h.worker()
 assert h.product()['on_hand']==48 and h.reconcile()['net_cents']==0

def test_after_sale_review_refund_and_retry_idempotency(h):
 o=h.pack(h.pay(h.order()));h.request('POST','/api/admin/orders/'+o['id']+'/pickup',{'code':o['pickup_code']},who='picker')
 path='/api/orders/'+o['id']+'/aftersale';body={'reason':'商品品质问题，请退款'}
 r=h.request('POST',path,body,key='after-sale-1');assert h.request('POST',path,body,key='after-sale-1')['id']==r['id']
 h.request('POST',path,body,key='after-sale-2',status=409)
 h.request('POST','/api/admin/refunds/'+r['id']+'/approve',{},who='picker',status=403)
 h.request('POST','/api/admin/refunds/'+r['id']+'/approve',{},who='manager');h.worker();h.worker()
 assert h.request('GET','/api/orders/'+o['id'])['state']=='refunded'
 assert h.product()['on_hand']==46 # Goods not automatically returned without receiving confirmation.
 assert h.reconcile()['ok']

def test_customer_and_cross_store_authorization(h):
 o=h.order()
 h.request('GET','/api/orders/'+o['id'],who='customer2',status=404)
 h.request('POST','/api/lab/pay/'+o['id'],{},who='customer2',status=404)
 h.request('GET','/api/admin/dashboard',status=403)
 h.request('GET','/api/orders/'+o['id'],who='other_store',status=404)
 h.request('POST','/api/admin/orders/'+o['id']+'/accept',{},who='other_store',status=404)
 h.request('GET','/api/orders/'+o['id'],who='rider',status=403)
 h.request('POST','/api/orders/'+o['id']+'/cancel',{},who='rider',status=403)
 h.request('GET','/api/lab/state',who='other_store',status=403)

def test_address_owner_delete_and_order_snapshot(h):
 h.request('DELETE','/api/addresses/1',who='customer2',status=404)
 o=h.order([{'sku_id':110,'quantity':1}],method='delivery',address_id=1)
 h.request('DELETE','/api/addresses/1')
 assert h.request('GET','/api/orders/'+o['id'])['address']['mobile']=='18800000001'

def test_inventory_movements_and_isolation(h):
 p=h.product();body={'sku_id':101,'delta':5,'reason':'purchase'}
 h.request('POST','/api/admin/inventory/adjust',body,who='manager',key='restock-1')
 h.request('POST','/api/admin/inventory/adjust',body,who='manager',key='restock-1')
 assert h.product()['on_hand']==p['on_hand']+5
 assert h.request('GET','/api/products/101?store_id=2')['on_hand']==48
 h.request('POST','/api/admin/inventory/adjust',{'sku_id':101,'delta':-2,'reason':'pos_sale'},who='manager',key='pos-event-1')
 h.request('POST','/api/admin/inventory/adjust',{'sku_id':101,'delta':-1,'reason':'writeoff'},who='manager',key='writeoff-1')
 assert h.product()['on_hand']==50 and h.reconcile()['ok']

def test_inventory_cannot_consume_reserved_units(h):
 o=h.order([{'sku_id':101,'quantity':48}])
 h.request('POST','/api/admin/inventory/adjust',{'sku_id':101,'delta':-1,'reason':'pos_sale'},who='manager',key='reserved-pos',status=409)
 assert h.product()['on_hand']==48 and h.reconcile()['ok']

def test_product_version_and_off_shelf_cart(h):
 h.request('PUT','/api/cart',{'sku_id':101,'quantity':1});p=h.product()
 h.request('PATCH','/api/admin/products/101',{'version':p['version'],'active':False},who='manager')
 h.request('PATCH','/api/admin/products/101',{'version':p['version'],'price_cents':10},who='manager',status=409)
 cart=h.request('GET','/api/cart');assert cart['subtotal_cents']==0
 h.request('POST','/api/quotes',{'items':[{'sku_id':101,'quantity':1}]},status=409)

def test_cart_invalid_when_stock_sold_in_pos(h):
 h.request('PUT','/api/cart',{'sku_id':101,'quantity':2})
 h.request('POST','/api/admin/inventory/adjust',{'sku_id':101,'delta':-48,'reason':'pos_sale'},who='manager',key='sold-all-pos')
 assert h.request('GET','/api/cart')['subtotal_cents']==0

def test_store_closed_refuses_checkout(h):
 s=h.request('GET','/api/store');h.request('PATCH','/api/admin/store',{'version':s['version'],'open':False},who='manager')
 h.request('POST','/api/quotes',{'items':[{'sku_id':101,'quantity':1}]},status=409)

def test_create_category_product_and_issue_coupon(h):
 category=h.request('POST','/api/admin/categories',{'name':'每日鲜花'},who='manager')
 p=h.request('POST','/api/admin/products',{'name':'测试鲜花','category_id':category['id'],'unit':'一束','price_cents':2990,'quantity':5,'barcode':'6901234500001'},who='manager')
 assert p['on_hand']==5
 h.request('POST','/api/admin/coupons',{'user_id':1,'minimum_cents':2000,'discount_cents':200},who='manager')
 assert len(h.request('GET','/api/coupons'))==4
 assert h.reconcile()['ok']

def test_favorites_toggle_and_isolation(h):
 assert h.request('PUT','/api/favorites/101')['selected']
 assert h.request('GET','/api/favorites')==[101]
 assert h.request('GET','/api/favorites',who='customer2')==[]
 assert not h.request('PUT','/api/favorites/101')['selected']

def test_database_reopen_and_backup_restore(h,tmp_path):
 o=h.pay(h.order());copy=tmp_path/'backup.sqlite3';h.app.state.db.backup(copy)
 for path in (h.app.state.db.path,str(copy)):
  app=create_app(path,KEY,SECRET,lab_enabled=True,clock=h.clock);c=TestClient(app)
  assert c.get('/api/orders/'+o['id'],headers=h.headers['customer']).json()['paid_cents']==796
  assert c.get('/api/admin/reconciliation',headers=h.headers['manager']).json()['ok']
  c.close()

def test_append_only_ledgers(h):
 with pytest.raises(sqlite3.IntegrityError):
  with h.app.state.db.tx() as c:c.execute('DELETE FROM stock_ledger WHERE id=1')
 h.order()
 with pytest.raises(sqlite3.IntegrityError):
  with h.app.state.db.tx() as c:c.execute('UPDATE audit SET action=\'forged\'')

def test_reconciliation_detects_corrupted_snapshot(h):
 with h.app.state.db.tx() as c:c.execute('UPDATE inventory SET on_hand=999 WHERE store_id=1 AND sku_id=101')
 result=h.reconcile();assert not result['ok'] and result['issues'][0]['type']=='inventory'

def test_export_excludes_customer_contact(h):
 h.pay(h.order([{'sku_id':110,'quantity':1}],method='delivery',address_id=1))
 export=h.request('GET','/api/admin/export',who='manager')
 assert '18800000001' not in json.dumps(export) and export['ok']

def test_security_headers_and_host(h):
 r=h.c.get('/api/health');assert r.headers['X-Frame-Options']=='DENY' and r.headers['Cache-Control']=='no-store'
 assert h.c.get('/api/health',headers={'Host':'attacker.example'}).status_code==400

def test_40_buyers_last_item_no_oversell(h):
 h.request('POST','/api/admin/inventory/adjust',{'sku_id':101,'delta':-47,'reason':'writeoff'},who='manager',key='last-unit-setup')
 quotes=[h.quote([{'sku_id':101,'quantity':1}]) for _ in range(40)]
 def submit(q):return h.c.post('/api/orders',json={'quote_id':q['id']},headers={**h.headers['customer'],'Idempotency-Key':'race-'+q['id']})
 with ThreadPoolExecutor(max_workers=20) as pool:results=list(pool.map(submit,quotes))
 assert [r.status_code for r in results].count(200)==1
 assert [r.status_code for r in results].count(409)==39
 assert h.product()['reserved']==1 and h.product()['available']==0
 h.pay(next(r.json() for r in results if r.status_code==200));assert h.product()['on_hand']==0 and h.reconcile()['ok']

def test_24_duplicate_payments_apply_once(h):
 o=h.order()
 def pay(_):return h.c.post('/api/lab/pay/'+o['id'],json={},headers=h.headers['customer'])
 with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(pay,range(24)))
 assert all(r.status_code==200 for r in results)
 assert h.product()['on_hand']==46 and len(h.sql("SELECT * FROM gateway_ledger WHERE kind='charge'"))==1
 h.worker();assert len(h.sql('SELECT * FROM print_receipts'))==1 and h.reconcile()['ok']

def test_12_competing_orders_cannot_double_spend_coupon(h):
 quotes=[h.quote([{'sku_id':110,'quantity':2}],coupon_id=1) for _ in range(12)]
 def submit(q):return h.c.post('/api/orders',json={'quote_id':q['id']},headers={**h.headers['customer'],'Idempotency-Key':'coupon-'+q['id']})
 with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(submit,quotes))
 assert [r.status_code for r in results].count(200)==1 and [r.status_code for r in results].count(409)==11
 assert h.reconcile()['ok']

def test_sample_order_is_idempotent_and_paid(h):
 a=h.request('POST','/api/lab/sample-order',{},who='manager',key='sample-repeat-01')
 b=h.request('POST','/api/lab/sample-order',{},who='manager',key='sample-repeat-01')
 assert a['order_id']==b['order_id']
 assert len(h.sql('SELECT * FROM orders'))==1
 assert len(h.sql("SELECT * FROM gateway_ledger WHERE kind='charge'"))==1
 h.worker();assert h.reconcile()['ok']

@pytest.mark.parametrize('who',['customer','customer2','picker','rider','other_store'])
def test_sample_order_limited_to_operator(h,who):
 h.request('POST','/api/lab/sample-order',{},who=who,key='sample-forbidden',status=403)

@pytest.mark.parametrize('quantity',[1,2,3,5,9])
def test_incremental_shortage_refund_is_exact_to_fen(h,quantity):
 o=h.order([{'sku_id':101,'quantity':quantity},{'sku_id':110,'quantity':2}],coupon_id=1)
 h.pay(o);h.request('POST',f'/api/admin/orders/{o["id"]}/accept',{},who='picker')
 line=next(i for i in o['items'] if i['sku_id']==101)
 for n in range(quantity):
  h.request('POST',f'/api/admin/orders/{o["id"]}/shortage',{'line_id':line['id'],'quantity':1},who='picker',key='shortage-part-'+str(n))
 h.worker()
 current=h.request('GET','/api/orders/'+o['id'])
 assert current['refunded_cents']==line['net_cents']
 assert h.reconcile()['ok']
