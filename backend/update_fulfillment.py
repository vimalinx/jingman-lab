"""Apply the merchant's Sep 13 rules once, backing up the exact database first.

Existing orders, source records, prices and manually adjusted stock are retained.
"""
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
import time

from .db import Database
from .fulfillment import DEFAULT_RULES, pickup_restriction
from .service import Retail, dump

MIGRATION = 'merchant-fulfillment-2026-09-13-v1'

def preflight(path):
    """Describe the migration without creating a database, backup or schema."""
    path=Path(path).resolve()
    if not path.is_file():raise ValueError('数据库不存在')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'data_migrations' in tables and c.execute('SELECT 1 FROM data_migrations WHERE name=?',(MIGRATION,)).fetchone():
            return {'mode':'preflight','already_applied':True}
        stores=[s for s,p in c.execute('SELECT store_id,public_json FROM store_profile') if json.loads(p).get('local_preview')]
        if not stores:raise ValueError('只允许迁移现有真实资料预览库')
        targets=[]
        for store in stores:
            for sku,name,category,weighed,price in c.execute('SELECT p.id,p.name,c.name,s.weighed,i.price_cents FROM products p JOIN categories c ON c.id=p.category_id JOIN inventory i ON i.sku_id=p.id LEFT JOIN product_sources s ON s.sku_id=p.id WHERE i.store_id=?',(store,)):
                reason=pickup_restriction(name,category.split(' / '),bool(weighed),price)
                if reason:targets.append({'store_id':store,'sku_id':sku,'reason':reason})
    return {'mode':'preflight','migration':MIGRATION,'pickup_only':targets,'rules':DEFAULT_RULES,'writes':False}

def apply(path):
    path=Path(path).resolve()
    if not path.is_file(): raise ValueError('数据库不存在')
    # Read-only discovery before any schema or data writes.
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'data_migrations' in tables and c.execute('SELECT 1 FROM data_migrations WHERE name=?',(MIGRATION,)).fetchone():
            return {'already_applied':True}
        profiles=c.execute('SELECT store_id,public_json FROM store_profile').fetchall()
        if not any(json.loads(p).get('local_preview') for _,p in profiles):raise ValueError('只允许迁移现有真实资料预览库')
        backup=path.with_name('before-'+MIGRATION+f'-{time.time_ns()}.sqlite3')
        fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        with sqlite3.connect(backup) as destination:c.backup(destination)
    db=Database(path);db.initialize(seed=False);engine=Retail(db)
    receipt={'backup':str(backup),'pickup_only':[],'released_areca':[],'stock_left_unchanged':[]}
    with db.tx() as c:
        if c.execute('SELECT 1 FROM data_migrations WHERE name=?',(MIGRATION,)).fetchone():return {'already_applied':True}
        for store,profile_json in profiles:
            profile=json.loads(profile_json)
            if not profile.get('local_preview'):continue
            profile['delivery_rules']={**DEFAULT_RULES,**profile.get('delivery_rules',{})}
            c.execute('UPDATE store_profile SET public_json=? WHERE store_id=?',(dump(profile),store))
            c.execute('UPDATE stores SET version=version+1 WHERE id=?',(store,))
            records=c.execute('SELECT p.id,p.name,c.name category,i.price_cents,i.on_hand,i.reserved,i.version,i.active,s.weighed,s.source_stock,s.review_json FROM products p JOIN categories c ON c.id=p.category_id JOIN inventory i ON i.sku_id=p.id LEFT JOIN product_sources s ON s.sku_id=p.id WHERE i.store_id=?',(store,)).fetchall()
            for r in records:
                reason=pickup_restriction(r['name'],r['category'].split(' / '),bool(r['weighed']),r['price_cents'])
                if not reason:continue
                c.execute('INSERT INTO product_fulfillment VALUES(?,?,NULL,1,?) ON CONFLICT(store_id,sku_id) DO UPDATE SET pickup_only=1,reason=excluded.reason',(store,r['id'],reason))
                receipt['pickup_only'].append(r['id'])
                source_issues=json.loads(r['review_json'] or '[]')
                if '槟榔' in r['name'] and '线上销售范围待审核' in source_issues:
                    c.execute('INSERT OR IGNORE INTO review_resolutions VALUES(?,?,?,?,?)',(store,r['id'],'线上销售范围待审核','商家确认：槟榔仅限自提，不配送',time.time()))
                    # Old importer held stock at zero. Restore only untouched opening stock,
                    # with a ledger entry; never re-import over orders or manual stock edits.
                    has_activity=c.execute("SELECT 1 FROM stock_ledger WHERE store_id=? AND sku_id=? AND reason!='opening'",(store,r['id'])).fetchone()
                    has_orders=c.execute('SELECT 1 FROM order_lines l JOIN orders o ON o.id=l.order_id WHERE o.store_id=? AND l.sku_id=?',(store,r['id'])).fetchone()
                    source_stock=Decimal(r['source_stock'])
                    if not engine.review_issues(c,r['id'],store) and not has_activity and not has_orders and r['version']==1 and not r['active'] and not r['on_hand'] and not r['reserved'] and source_stock>=0 and source_stock==source_stock.to_integral_value():
                        if source_stock:engine.stock(c,store,r['id'],int(source_stock),0,'channel_approval',MIGRATION)
                        c.execute("UPDATE inventory SET active=1 WHERE store_id=? AND sku_id=?",(store,r['id']))
                        c.execute("UPDATE products SET tag='仅限自提',description='门店商品快照。槟榔仅限到店自提，不配送。' WHERE id=?",(r['id'],))
                        receipt['released_areca'].append(r['id'])
                    else:receipt['stock_left_unchanged'].append(r['id'])
                c.execute('UPDATE inventory SET version=version+1 WHERE store_id=? AND sku_id=?',(store,r['id']))
            engine.audit(c,None,'store.fulfillment_migrated',store,{'migration':MIGRATION,'rules':profile['delivery_rules']},store)
        c.execute('INSERT INTO data_migrations VALUES(?,?,?)',(MIGRATION,time.time(),dump(receipt)))
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('database',type=Path)
    p.add_argument('--apply',action='store_true',help='Apply after reviewing the default read-only preflight')
    args=p.parse_args();os.umask(0o077)
    print(json.dumps((apply if args.apply else preflight)(args.database),ensure_ascii=False,indent=2))
