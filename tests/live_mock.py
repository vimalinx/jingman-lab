"""Signed mock HTTP checks against the running, local-only acceptance service.
Only scenario switches and sessions are changed; scenarios are restored.
"""
import json
import os
from pathlib import Path
import httpx

def main():
    key=json.loads((Path(os.environ['LOCALAPPDATA'])/'JingmanAcceptance/app/credentials.json').read_text())['access_key']
    with httpx.Client(base_url='http://127.0.0.1:8874',timeout=10,trust_env=False) as client:
        login=client.post('/api/session',json={'access_key':key,'persona':'manager'})
        login.raise_for_status()
        client.headers['Authorization']='Bearer '+login.json()['token']
        results=[]
        try:
            for scenario,expected in [('success',200),('empty',200),('business-error',502),('bad-signature',502),('wrong-sid',502),('stale',502),('http203',502),('timeout',504)]:
                change=client.put('/api/admin/lakala-mock/scenario',json={'scenario':scenario})
                assert change.status_code==200,change.text
                result=client.post('/api/admin/lakala-mock/query',json={'barcode':'9900000000001'})
                assert result.status_code==expected,(scenario,result.status_code,result.text)
                if scenario=='success':
                    assert result.json()['verified'] and result.json()['data']['saleProduct'][0]['unitPrice']==200
                if scenario=='empty': assert result.json()['data']['saleProduct']==[]
                results.append({'scenario':scenario,'http_status':result.status_code,'passed':True})
        finally:
            client.put('/api/admin/lakala-mock/scenario',json={'scenario':'success'}).raise_for_status()
            client.delete('/api/session')
        print(json.dumps({'passed':True,'real_provider_called':False,'inventory_written':False,'cases':results},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
