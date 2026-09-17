"""Download only reviewed catalogue images to private local storage.

No redirects, cookies, credentials or arbitrary remote URLs are supported.
"""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import urllib.request
from urllib.parse import urlsplit
from PIL import Image
from .catalog_import import IMAGE_HOST

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def cache(data_dir):
    data_dir=Path(data_dir)
    image_dir=data_dir/'product-images';image_dir.mkdir(mode=0o700,exist_ok=True)
    with sqlite3.connect(data_dir/'jingman.sqlite3') as c:
        records=c.execute('SELECT sku_id,image_url FROM product_sources WHERE image_url!=?',('',)).fetchall()
    def fetch(record):
        sku,url=record
        target=image_dir/f'{sku}.webp'
        if target.is_file():return sku,True
        try:
            u=urlsplit(url)
            if u.scheme!='https' or u.hostname!=IMAGE_HOST or u.username or u.password or u.port not in (None,443):raise ValueError('source')
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            with opener.open(url,timeout=15) as response:
                raw=response.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:raise ValueError('size')
            with Image.open(BytesIO(raw)) as im:
                if im.width*im.height>20000000:raise ValueError('pixels')
                im.thumbnail((700,700))
                with target.open('xb') as f:
                    os.chmod(target,0o600);im.convert('RGB').save(f,format='WEBP',quality=82)
            return sku,True
        except Exception:
            return sku,False
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(fetch,records))
    with sqlite3.connect(data_dir/'jingman.sqlite3') as c:
        for sku,ok in results:
            if ok:c.execute('UPDATE products SET image=? WHERE id=?',(f'catalog/{sku}',sku))
    report={'cached':sum(ok for _,ok in results),'failed_skus':[sku for sku,ok in results if not ok]}
    with (data_dir/'image-report.json').open('w') as f:
        os.chmod(f.name,0o600);json.dump(report,f)
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('data_dir',type=Path)
    os.umask(0o077);print(json.dumps(cache(p.parse_args().data_dir)))
