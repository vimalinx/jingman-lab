"""Browser DOM + live HTTP harness. No response data is fabricated here.

In a restricted renderer that forbids top-level navigation, --renderer mode
injects the exact local HTML/CSS/JS, provides isolated sessionStorage, and
forwards fetch('/api/...') through httpx to the listening backend. Assets load
from that backend. This is NOT a WeChat device or full-browser-network test.
The ordinary mode navigates to the real localhost URL without any shims.
"""
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]

def load(page,base,key,renderer=False):
 if not renderer:
  page.goto(base+'/#access='+key,wait_until='networkidle')
  return
 client=httpx.Client(base_url=base,timeout=25)
 def bridge(url,options):
  if not isinstance(url,str) or not url.startswith('/api/') or '://' in url:
   raise ValueError('Renderer bridge only permits the local application API')
  res=client.request(options.get('method','GET'),url,headers=options.get('headers',{}),content=options.get('body'))
  return {'status':res.status_code,'body':res.text}
 page.expose_function('__jingmanHTTP',bridge)
 markup=(ROOT/'web/index.html').read_text()
 import re
 markup=re.sub(r'<script.*?</script>','',markup)
 markup=re.sub(r'<link[^>]*>','',markup)
 markup=markup.replace('<head>',f'<head><base href="{base}/">')
 page.set_content(markup)
 page.add_style_tag(content=(ROOT/'web/style.css').read_text())
 page.evaluate('''() => {
  const state=new Map(); Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>state.get(k)||null,setItem:(k,v)=>state.set(k,String(v)),removeItem:k=>state.delete(k),clear:()=>state.clear()}});
  document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(a&&a.getAttribute('href').startsWith('#')&&!a.dataset.action){e.preventDefault();location.hash=a.getAttribute('href')}},true);
  window.fetch=async (url,options={})=>{const r=await window.__jingmanHTTP(url,options);return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>JSON.parse(r.body)}};
 }''')
 page.evaluate('(k)=>{sessionStorage.setItem("jm-key",k);location.hash="/home"}',key)
 page.add_script_tag(content=(ROOT/'web/shared.js').read_text())
 page.add_script_tag(content=(ROOT/'web/app.js').read_text())
 page.locator('[data-form=login] input').fill(key)
 page.locator('[data-form=login] button').click()
 page.wait_for_selector('main.main')
 return client
