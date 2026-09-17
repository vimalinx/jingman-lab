from datetime import datetime, timezone, timedelta
import json
import sqlite3
from pathlib import Path

import pytest

from backend.fulfillment import DEFAULT_RULES, extra_fee, pickup_restriction
from backend.update_fulfillment import apply, preflight


def at(h, hour, minute=0, second=0):
    h.clock.value=datetime(2026,9,13,hour,minute,second,tzinfo=timezone(timedelta(hours=8))).timestamp()


@pytest.fixture
def delivery(h):
    at(h,8)
    with h.app.state.db.tx() as c:
        c.execute('UPDATE sessions SET expires=?',(h.clock.value+86400,))
        c.execute('INSERT INTO store_profile VALUES(1,?)',(json.dumps({'local_preview':True,'delivery_confirmed':True,'delivery_rules':DEFAULT_RULES}),))
        c.execute('UPDATE stores SET minimum_cents=2000,delivery_cents=200,free_shipping_cents=3000 WHERE id=1')
        c.execute('UPDATE inventory SET price_cents=3000 WHERE store_id=1 AND sku_id IN(101,102)')
        c.execute('UPDATE coupons SET expires=?',(h.clock.value+86400,))
    return h


def weight(h,grams,sku=101):
    p=h.product(sku)
    return h.request('PATCH',f'/api/admin/products/{sku}/fulfillment',{'version':p['version'],'weight_g':grams},who='manager')


def dq(h,**kw):
    return h.quote(items=[{'sku_id':101,'quantity':1}],method='delivery',address_id=1,**kw)


@pytest.mark.parametrize('grams,expected',[(4999,0),(5000,0),(5001,150),(5200,150),(6000,150),(6001,300),(7200,450)])
def test_weight_boundary_and_free_base(delivery,grams,expected):
    h=delivery;weight(h,grams);q=dq(h)
    assert q['shipping_detail']['weight_g']==grams
    assert q['shipping_detail']['base_cents']==0
    assert q['shipping_detail']['extra_weight_cents']==expected
    assert q['total_cents']==3000+expected


def test_proportional_rounding_available():
    rules={**DEFAULT_RULES,'rounding':'proportional'}
    assert extra_fee(5200,rules)==30
    assert extra_fee(5000,rules)==0
    assert extra_fee(5010,rules)==2


def test_multi_sku_quantity_and_coupon_do_not_erase_surcharge(delivery):
    h=delivery;weight(h,2000);weight(h,1500,102)
    q=h.quote(items=[{'sku_id':101,'quantity':2},{'sku_id':102,'quantity':1}],method='delivery',address_id=1,coupon_id=1)
    assert q['shipping_detail']['weight_g']==5500
    assert q['shipping_cents']==150
    assert q['discount_cents']==300
    # A coupon that drops merchandise below 30 adds the base fee, plus weight fee.
    weight(h,6000)
    q=dq(h,coupon_id=1)
    assert q['shipping_detail']['base_cents']==200
    assert q['shipping_detail']['extra_weight_cents']==150
    assert q['total_cents']==3050


@pytest.mark.parametrize('hour,minute,second,allowed',[(7,29,59,False),(7,30,0,True),(21,59,59,True),(22,0,0,False)])
def test_beijing_delivery_hours_pickup_unaffected(delivery,hour,minute,second,allowed):
    h=delivery;at(h,hour,minute,second);weight(h,100)
    h.quote(items=[{'sku_id':101,'quantity':1}])
    if allowed:dq(h)
    else:
        result=h.request('POST','/api/quotes',{'items':[{'sku_id':101,'quantity':1}],'method':'delivery','address_id':1},status=422)
        assert result['error']['code']=='delivery_hours'


def test_time_rechecked_at_order_creation(delivery):
    h=delivery;at(h,21,59,50);weight(h,100);q=dq(h);h.clock.advance(10)
    result=h.request('POST','/api/orders',{'quote_id':q['id']},key='at-closing-time',status=422)
    assert result['error']['code']=='delivery_hours'
    assert not h.sql('SELECT id FROM orders')


def test_missing_weight_is_not_zero_and_pickup_is_allowed(delivery):
    h=delivery
    result=h.request('POST','/api/quotes',{'items':[{'sku_id':101,'quantity':1}],'method':'delivery','address_id':1},status=422)
    assert result['error']['code']=='weight_required'
    assert h.quote()['shipping_cents']==0


def test_pickup_only_rejected_in_mixed_cart_and_quote_recalculation(delivery):
    h=delivery;weight(h,100);weight(h,100,102);q=dq(h)
    p=h.product()
    h.request('PATCH','/api/admin/products/101/fulfillment',{'version':p['version'],'pickup_only':True},who='manager')
    assert h.quote()['shipping_cents']==0
    result=h.request('POST','/api/quotes',{'items':[{'sku_id':101,'quantity':1},{'sku_id':102,'quantity':1}],'method':'delivery','address_id':1},status=422)
    assert result['error']['code']=='pickup_only'
    h.request('POST','/api/orders',{'quote_id':q['id']},key='changed-channel',status=422)
    assert not h.sql('SELECT id FROM orders')


def test_changed_weight_invalidates_quote_but_not_existing_order(delivery):
    h=delivery;weight(h,5100);q=dq(h)
    o=h.request('POST','/api/orders',{'quote_id':q['id']},key='order-snapshot')
    assert o['shipping_detail']['extra_weight_cents']==150
    q2=dq(h);weight(h,6100)
    result=h.request('POST','/api/orders',{'quote_id':q2['id']},key='changed-weight',status=409)
    assert result['error']['code']=='quote_changed'
    old=h.request('GET','/api/orders/'+o['id'])
    assert old['shipping_detail']['weight_g']==5100
    assert old['shipping_cents']==150


def test_weight_edit_permissions_and_validation(delivery):
    h=delivery
    for who in ('customer','picker','rider'):
        h.request('PATCH','/api/admin/products/101/fulfillment',{'version':1,'weight_g':100},who=who,status=403)
    h.request('PATCH','/api/admin/products/101/fulfillment',{'version':1,'weight_g':100},who='other_store',status=200)
    assert h.product()['weight_g'] is None  # Other manager can only change their own stock row.
    for invalid in (-1,0,1.5,True,1000001):
        h.request('PATCH','/api/admin/products/101/fulfillment',{'version':1,'weight_g':invalid},who='manager',status=422)
    weight(h,123)
    h.request('PATCH','/api/admin/products/101/fulfillment',{'version':1,'weight_g':456},who='manager',status=409)
    weight(h,None)
    assert h.product()['weight_g'] is None


def test_new_areca_and_bulk_category_cannot_enable_delivery(delivery):
    h=delivery
    p=h.request('POST','/api/admin/products',{'name':'测试槟榔','category_id':4,'unit':'包','price_cents':3000,'quantity':5,'barcode':'6937962134778'},who='manager')
    assert p['pickup_only']==1
    h.request('PATCH',f'/api/admin/products/{p["id"]}/fulfillment',{'version':p['version'],'pickup_only':False},who='manager',status=422)
    h.quote(items=[{'sku_id':p['id'],'quantity':1}])
    assert pickup_restriction('混合零食',['散装零食'],True,1980)
    assert pickup_restriction('兰花豆',['休闲食品','坚果炒货'],True,1980)
    assert not pickup_restriction('袋装零食',['休闲食品'],False,1980)
    assert not pickup_restriction('无烟蚊香',['清洁日化'],False,900)


def test_single_coupon_atomic_reservation_and_no_client_weight(delivery):
    h=delivery;weight(h,5000);q1=dq(h,coupon_id=1);q2=dq(h,coupon_id=1)
    o=h.request('POST','/api/orders',{'quote_id':q1['id']},key='coupon-first')
    h.request('POST','/api/orders',{'quote_id':q2['id']},key='coupon-second',status=409)
    repeat=h.request('POST','/api/orders',{'quote_id':q1['id']},key='coupon-first')
    assert o['id']==repeat['id']
    assert len(h.sql('SELECT id FROM orders'))==1
    for extra in ({'coupon_ids':[1,2]},{'weight_g':0},{'shipping_cents':0}):
        h.request('POST','/api/quotes',{'items':[{'sku_id':101,'quantity':1}],**extra},status=422)


def test_migration_backed_up_idempotent_preserves_source_and_manual_stock(h):
    with h.app.state.db.tx() as c:
        c.execute('INSERT INTO store_profile VALUES(1,?)',(json.dumps({'local_preview':True,'delivery_confirmed':False}),))
        c.execute("INSERT INTO import_batches VALUES('fixture',0,'{}')")
        for sku in (101,102):
            c.execute("UPDATE products SET name='测试槟榔' WHERE id=?",(sku,))
            c.execute('INSERT INTO product_sources VALUES(?,?,?,?,?,?,?,?)',(sku,'fixture',str(sku),sku,'5',0,json.dumps(['线上销售范围待审核']),''))
            # A prior import with all stock held at zero; ledger stays reconciled.
            qty=c.execute('SELECT on_hand FROM inventory WHERE store_id=1 AND sku_id=?',(sku,)).fetchone()[0]
            # Seed ledger is append-only, so simulate this as zero via adjustments,
            # which the migration must recognize as activity and never overwrite.
            h.app.state.engine.stock(c,1,sku,-qty,0,'stocktake','fixture')
            c.execute('UPDATE inventory SET active=0 WHERE store_id=1 AND sku_id=?',(sku,))
    before=h.sql('SELECT * FROM product_sources');prices=h.sql('SELECT price_cents,on_hand FROM inventory WHERE store_id=1')
    schema_before=h.sql("SELECT name,sql FROM sqlite_master ORDER BY name")
    preview=preflight(h.app.state.db.path)
    assert preview['writes'] is False
    assert [p['sku_id'] for p in preview['pickup_only']]==[101,102]
    assert not list(Path(h.app.state.db.path).parent.glob('before-merchant-fulfillment-*'))
    assert h.sql("SELECT name,sql FROM sqlite_master ORDER BY name")==schema_before
    assert h.sql('SELECT * FROM product_sources')==before
    assert h.sql('SELECT price_cents,on_hand FROM inventory WHERE store_id=1')==prices
    receipt=apply(h.app.state.db.path)
    assert receipt['released_areca']==[]
    assert receipt['stock_left_unchanged']==[101,102]
    assert h.sql('SELECT * FROM product_sources')==before
    assert h.sql('SELECT price_cents,on_hand FROM inventory WHERE store_id=1')==prices
    assert apply(h.app.state.db.path)=={'already_applied':True}
    with sqlite3.connect(receipt['backup']) as c:
        assert not c.execute('SELECT * FROM data_migrations').fetchall()
    assert h.reconcile()['ok']
