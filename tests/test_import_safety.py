import json
import os
from unittest.mock import patch

import pytest
from backend.catalog_import import build

def record(**kw):
    return dict(row=2,source_sku='12345678',barcode='6937962134778',name='测试商品',
        unit='袋',price_cents=300,stock='8',weighed=False,categories=['食品'],
        image_url='',issues=[],active=True,quantity=8,**kw)

def test_new_database_only_and_sources_private(tmp_path):
    source=tmp_path/'source.xlsx';source.write_bytes(b'fixture')
    dest=tmp_path/'private'
    with patch('backend.catalog_import.inspect',return_value=[record()]):
        result=build(source,dest,True)
        assert result['total']==1
        with pytest.raises(FileExistsError):build(source,dest,True)
    # POSIX mode assertions do not represent Windows ACLs. Keep business checks
    # below active on Windows; do not skip the entire import-safety test.
    if os.name != 'nt':
        assert os.stat(dest).st_mode & 0o777 == 0o700
        assert os.stat(dest/'jingman.sqlite3').st_mode & 0o777 == 0o600
    from fastapi.testclient import TestClient
    from backend.app import create_app
    with TestClient(create_app(dest/'jingman.sqlite3','a'*32,'b'*40,lab_enabled=True)) as c:
        assert c.get('/api/admin/import-review').status_code==401
        profile=c.get('/api/store').json()
        assert profile['delivery_confirmed'] is False
        assert 'source_stock' not in c.get('/api/products').text

def local(h):
    with h.app.state.db.tx() as c:
        c.execute('INSERT INTO store_profile VALUES(1,?)',(json.dumps({'local_preview':True,'delivery_confirmed':True}),))

def test_paid_pickup_cancel_once(h):
    local(h);o=h.order();h.pay(o)
    before=h.product()['on_hand']
    for _ in range(2):h.request('POST','/api/orders/'+o['id']+'/cancel',{})
    h.worker()
    assert h.product()['on_hand']==before+2
    assert h.reconcile()['ok']

def test_dispatched_cancel_keeps_fee_and_does_not_restore_goods(h):
    local(h)
    o=h.order(items=[{'sku_id':101,'quantity':10}],method='delivery',address_id=1)
    h.pay(o);h.pack(o)
    d=h.request('POST','/api/admin/orders/'+o['id']+'/dispatch',{},who='manager')
    for state in ['accepted','picked_up']:
        h.request('POST',f'/api/lab/delivery/{d["id"]}/{state}',{},who='manager')
    before=h.product()['on_hand']
    for _ in range(2):h.request('POST','/api/orders/'+o['id']+'/cancel',{})
    h.worker();after=h.request('GET','/api/orders/'+o['id'])
    assert after['paid_cents']-after['refunded_cents']==200
    assert after['state']=='cancelled'
    assert h.product()['on_hand']==before
    assert h.reconcile()['ok']
    h.request('POST',f'/api/lab/delivery/{d["id"]}/delivered',{},who='manager',status=409)
