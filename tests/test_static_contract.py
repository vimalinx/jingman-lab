"""Local source/route/asset checks, NOT the proprietary WeChat compiler."""
import json,re
from pathlib import Path
from html.parser import HTMLParser
from fastapi.testclient import TestClient
from backend.app import create_app
from conftest import KEY,SECRET
ROOT=Path(__file__).resolve().parents[1]
class Balance(HTMLParser):
 def __init__(self):super().__init__();self.stack=[]
 def handle_starttag(self,tag,attrs):self.stack.append(tag)
 def handle_startendtag(self,tag,attrs):pass
 def handle_endtag(self,tag):assert self.stack.pop()==tag

def test_all_native_wxml_tags_balance():
 for p in (ROOT/'miniprogram').rglob('*.wxml'):
  parser=Balance();parser.feed(p.read_text());assert not parser.stack,p

def test_static_ui_and_offline_api_contract(tmp_path):
 with TestClient(create_app(tmp_path/'web.sqlite3',KEY,SECRET,lab_enabled=True,web_dir=ROOT/'web')) as client:
  for route in ['/','/app.js','/shared.js','/style.css','/assets/hero.webp','/assets/banana.webp','/api-reference.html','/api-reference.js','/openapi.json']:
   r=client.get(route);assert r.status_code==200,route
   assert 'Content-Security-Policy' in r.headers
  r=client.get('/docs');assert r.status_code==200 and 'OFFLINE API REFERENCE' in r.text
  assert client.get('/../backend/schema.sql').status_code==404
  assert client.get('/assets/not-found.webp').status_code==404

def test_catalogue_assets_exist():
 from backend.db import CATALOG
 for product in CATALOG:assert (ROOT/'web/assets'/f'{product[8]}.webp').is_file()

def test_clients_have_no_real_payment_call():
 # Production hooks must not accidentally become active in an explicit lab release.
 mp='\n'.join(p.read_text() for p in (ROOT/'miniprogram').rglob('*.js'))
 assert 'wx.requestPayment(' not in mp and 'wx.login(' not in mp
 assert '/simulate' in mp and '/payments/' in mp
 assert 'APP_SECRET' not in mp
