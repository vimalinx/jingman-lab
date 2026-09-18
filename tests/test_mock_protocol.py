import json
import time
import pytest
from fastapi.testclient import TestClient
from backend.lakala_mock import initialize, create_mock, private_key, public_key, sign
from backend.lakala_readonly import encode_request, verify_response, IntegrationBlocked


@pytest.fixture
def protocol(tmp_path):
    directory = tmp_path/'mock'
    initialize(directory, 8873)
    client_config = json.loads((directory/'client.json').read_text())
    return directory, client_config


def request(config):
    stamp = int(time.time()*1000)
    raw = encode_request(config, '9900000000001', 'test-request', stamp)
    return raw, {'X-Client-Sign':sign(private_key(config['private_key_file']),raw),'Content-Type':'application/json'}


def test_signed_mock_and_runtime_scenario(protocol):
    directory, config = protocol
    raw, headers = request(config)
    with TestClient(create_mock(directory/'server.json')) as client:
        r = client.post('/b2c-oms-server/productShop/barcodeQuery',content=raw,headers=headers)
        data = verify_response(r.content,r.headers['X-Server-Sign'],public_key(config['server_public_key_file']),'test-request',r.status_code,int(time.time()*1000))
        assert data['saleProduct'][0]['unitPrice']==200
        (directory/'scenario.json').write_text(json.dumps({'scenario':'empty'}))
        r=client.post('/b2c-oms-server/productShop/barcodeQuery',content=raw,headers=headers)
        assert r.json()['saleProduct']==[]
        bad=client.post('/b2c-oms-server/productShop/barcodeQuery',content=raw+b' ',headers=headers)
        assert bad.status_code==403
        assert client.post('/b2c-oms-server/productShop/edit',json={}).status_code==404


@pytest.mark.parametrize('scenario',['business-error','bad-signature','wrong-sid','stale','http203'])
def test_mock_rejects_invalid_provider_result(protocol,scenario):
    directory, config = protocol
    raw, headers = request(config)
    with TestClient(create_mock(directory/'server.json',scenario)) as client:
        r=client.post('/b2c-oms-server/productShop/barcodeQuery',content=raw,headers=headers)
        with pytest.raises(IntegrationBlocked):
            verify_response(r.content,r.headers['X-Server-Sign'],public_key(config['server_public_key_file']),'test-request',r.status_code,int(time.time()*1000))


def test_mock_scenario_requires_operator(h):
    for actor in ['customer','picker','other_store']:
        h.request('PUT','/api/admin/lakala-mock/scenario',{'scenario':'success'},who=actor,status=403)
    h.request('PUT','/api/admin/lakala-mock/scenario',{'scenario':'success'},who='manager',status=409)
