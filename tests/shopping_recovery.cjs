// Exercise the shipped submission recovery functions, including a lost response.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const code=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const storage=new Map(),calls=[];let mode='lost',navigated=null;
const sandbox={S:{user:{id:1},checkout:[{sku_id:101,quantity:1}]},
 sessionStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k)||null,removeItem:k=>storage.delete(k)},
 api:async(p,m,b,key)=>{calls.push({p,b,key});if(mode==='lost')throw new Error('Response lost');if(mode==='expired'){const e=new Error('Quote expired');e.code='quote_expired';throw e;}return {id:'one-order'};},
 render:async()=>{},go:(p,q)=>{navigated={p,q};},toast:()=>{}};
vm.createContext(sandbox);
vm.runInContext(code.slice(code.indexOf('function saveCheckoutPreferences()')),sandbox);
(async()=>{
 const attempt={quote_id:'same-quote',key:'same-key'};
 await assert.rejects(sandbox.submitShoppingOrder(attempt),/Response lost/);
 assert.equal(sandbox.readPendingOrder().key,'same-key');
 mode='ok';await sandbox.submitShoppingOrder(sandbox.readPendingOrder());
 assert.equal(calls.length,2);assert.equal(calls[0].key,calls[1].key);
 assert.equal(navigated.q.id,'one-order');assert.equal(sandbox.readPendingOrder(),null);
 mode='expired';await assert.rejects(sandbox.submitShoppingOrder(attempt),/Quote expired/);
 assert.equal(sandbox.readPendingOrder(),null);
 mode='lost';await assert.rejects(sandbox.submitShoppingOrder(attempt));
 sandbox.S.user.id=2;assert.equal(sandbox.readPendingOrder(),null);
 console.log('PASS: lost-response retry reuses key; success clears; expired quote resets; account isolation');
})().catch(e=>{console.error(e);process.exitCode=1;});
