/* Executes the shipped native Page handlers with wx.request mapped to LIVE HTTP.
   WXML bindings/routes are checked, not rendered by a WeChat runtime. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..'),MP=path.join(ROOT,'miniprogram');
const EVIDENCE=process.env.JINGMAN_NATIVE_EVIDENCE_DIR||path.join(ROOT,'evidence');
fs.mkdirSync(EVIDENCE,{recursive:true});
const base=process.argv[2]||'http://127.0.0.1:8765',access=JSON.parse(fs.readFileSync(process.argv[3],'utf8')).access_key;
const state=new Map(),toasts=[],steps=[];let lastNavigation='';
global.wx={getStorageSync:k=>state.get(k)||'',setStorageSync:(k,v)=>state.set(k,v),removeStorageSync:k=>state.delete(k),getStorageInfoSync:()=>({keys:[...state.keys()]}),pageScrollTo:()=>{},showToast:v=>toasts.push(v),showModal:v=>{toasts.push(v);v.success?.({confirm:true})},switchTab:v=>{lastNavigation=v.url},navigateTo:v=>{lastNavigation=v.url},reLaunch:v=>{lastNavigation=v.url;v.complete?.()},request:o=>{
 fetch(o.url,{method:o.method,headers:o.header,body:o.data===undefined?undefined:JSON.stringify(o.data)}).then(async r=>o.success({statusCode:r.status,data:await r.json()})).catch(e=>o.fail({errMsg:e.message}));
}};
const A=require(MP+'/utils/api');
function page(name){let def;global.Page=d=>def=d;const fn=MP+'/pages/'+name+'/index.js';delete require.cache[require.resolve(fn)];require(fn);const p={...def,data:structuredClone(def.data),setData(data){Object.assign(this.data,data)}};return p}
const tap=data=>({currentTarget:{dataset:data||{}},detail:{}});
const value=data=>({detail:{value:data}});
const pass=name=>{steps.push({name,passed:true});console.log('PASS',name)};
async function invoke(p,method,...args){assert.equal(typeof p[method],'function');const result=await p[method](...args);if(result?.failed)throw result.error;return result}
async function login(role){await A.login(access,role)}
(async()=>{
 try{
  state.set('jm-base',base);
  const cfg=JSON.parse(fs.readFileSync(MP+'/app.json','utf8'));
  assert.equal(cfg.pages.length,15);
  for(const route of cfg.pages){for(const ext of ['.js','.json','.wxml','.wxss'])assert.ok(fs.existsSync(MP+'/'+route+ext),route+ext);
   const name=route.split('/')[1],p=page(name),xml=fs.readFileSync(MP+'/'+route+'.wxml','utf8');
   for(const match of xml.matchAll(/\b(?:bind|catch)(?:tap|submit|change|confirm|input)="(\w+)"/g))assert.equal(typeof p[match[1]],'function',`${name}.${match[1]}`);
   for(const match of xml.matchAll(/<(?:include|import) src="([^\"]+)"/g))assert.ok(fs.existsSync(path.resolve(MP,path.dirname(route),match[1])));
  }
  for(const t of cfg.tabBar.list)assert.ok(cfg.pages.includes(t.pagePath));
  pass('15个原生页面文件齐全，WXML事件绑定、引用和Tab路由一致');
  const F=require(MP+'/utils/format');assert.equal(F.money(398),'3.98');assert.equal(F.yuanToFen('0.29'),29);assert.throws(()=>F.yuanToFen('1.999'));assert.throws(()=>F.money(1.1));assert.equal(F.phoneEncryption('18800000001'),'188****0001');pass('双端复用金额格式化与脱敏，拒绝小数分');
  const connect=page('connect');await invoke(connect,'onLoad');await invoke(connect,'submit',value({base,key:access}));assert.equal(A.user().id,1);assert.match(lastNavigation,/home/);pass('原生连接页通过真实HTTP登录顾客');
  const h=page('home');await invoke(h,'onShow');assert.equal(h.data.products.length,12);assert.ok(h.data.products.every(p=>p.active&&p.available>0));assert.ok(!h.data.products.some(p=>p.id===108));pass('原生首页最多推荐12个在售有库存商品，不推荐售罄商品');
  const cat=page('category');await invoke(cat,'onShow');await invoke(cat,'search',value('牛奶'));assert.equal(cat.data.products.length,1);assert.equal(cat.data.products[0].id,110);pass('原生分类搜索调用后端筛选');
  const product=page('product');await invoke(product,'onLoad',{id:103});await invoke(product,'variant',tap({id:115}));assert.equal(product.data.p.unit,'500g');await invoke(product,'favorite');assert.ok((await A.call('/favorites')).includes(115));pass('原生商品规格切换及收藏API持久化');
  await invoke(h,'add',tap({id:101}));await invoke(h,'add',tap({id:110}));const cart=page('cart');await invoke(cart,'onShow');await invoke(cart,'quantity',tap({id:101,delta:1}));assert.equal(cart.data.total,'30.74');await invoke(cart,'checkout');pass('原生购物车增减数量并真实结算');
  const checkout=page('checkout');await invoke(checkout,'onLoad');await invoke(checkout,'method',tap({method:'delivery'}));await invoke(checkout,'coupon',value('1'));assert.equal(checkout.data.quote.total,'30.74');await invoke(checkout,'submit');const oid=new URL('http://local'+lastNavigation).searchParams.get('id');assert.ok(oid);pass('原生配送、优惠、服务端报价与库存预占');
  const detail=page('detail');await invoke(detail,'onLoad',{id:oid});const failed=await detail.pay(tap({success:false}));assert.ok(failed.failed);assert.equal((await A.call('/orders/'+oid)).state,'pending_payment');await invoke(detail,'pay',tap({success:true}));assert.equal(detail.data.o.state,'paid');pass('原生模拟支付失败/成功两分支');
  await login('manager');const lab=page('lab');await invoke(lab,'onShow');await invoke(lab,'fault',{currentTarget:{dataset:{key:'refund_failure'}},detail:{value:true}});pass('原生实验室开启退款故障');
  await login('picker');const staff=page('detail');await invoke(staff,'onLoad',{id:oid});await invoke(staff,'accept');await invoke(staff,'shortage',tap({line:staff.data.o.items.find(l=>l.sku_id===101).id}));await invoke(staff,'pick');await invoke(staff,'ready');assert.equal(staff.data.o.state,'ready');pass('原生店员接单、缺1件退款、拣齐与打包');
  await login('manager');await invoke(lab,'worker');assert.ok(lab.data.jobs.some(j=>j.kind==='refund'&&j.state==='failed'));await invoke(lab,'fault',{currentTarget:{dataset:{key:'refund_failure'}},detail:{value:false}});await invoke(lab,'worker');assert.ok(lab.data.report.ok);pass('原生失败退款重试后真实账本一致');
  await invoke(staff,'dispatch');const did=staff.data.o.delivery.id;await login('rider');const rider=page('rider');await invoke(rider,'onShow');assert.match(rider.data.tasks[0].mobile_masked,/\*\*\*\*/);for(const s of ['accepted','picked_up','delivered'])await invoke(rider,'advance',tap({id:did,state:s}));pass('原生配送员脱敏任务与完整模拟配送回调');
  await login('customer');await invoke(detail,'load');assert.equal(detail.data.o.state,'completed');assert.ok(detail.data.o.refunded_cents>0);await invoke(detail,'aftersale',value({reason:'原生控制器验收售后'}));const rid=detail.data.o.refunds.find(r=>r.state==='requested').id;pass('原生顾客查看送达、缺货退款并提交售后');
  await login('manager');await invoke(staff,'load');await invoke(staff,'approve',tap({id:rid}));await invoke(lab,'worker');assert.ok(lab.data.report.ok);pass('原生店长审核售后、退款队列执行与对账');
  const inv=page('inventory');await invoke(inv,'onShow');const before=inv.data.items.find(p=>p.id===101).on_hand;await invoke(inv,'edit',tap({id:101}));await invoke(inv,'reason',value('2'));await invoke(inv,'save',value({quantity:'1'}));assert.equal(inv.data.items.find(p=>p.id===101).on_hand,before-1);pass('原生模拟POS扣库存并写入流水');
  const work=page('workbench');await invoke(work,'onShow');assert.equal(work.data.d.order_count,1);pass('原生店长工作台使用数据库实数');
  await login('customer');const addr=page('addresses');await invoke(addr,'onShow');await invoke(addr,'create');await invoke(addr,'save',value({...addr.data.editing,name:'验收顾客',mobile:'18800000003',address:'虚构验收小区2号楼201',latitude:'31.234',longitude:'121.48'}));assert.equal(addr.data.items.length,2);const added=addr.data.items.at(-1);await invoke(addr,'edit',tap({id:added.id}));await invoke(addr,'save',value({...added,address:'修改后的虚构地址101',latitude:'31.234',longitude:'121.48'}));await invoke(addr,'remove',tap({id:added.id}));assert.equal(addr.data.items.length,1);pass('原生手动地址新增、编辑与删除，无定位依赖');
  const profile=page('profile');await invoke(profile,'onShow');assert.equal(profile.data.count,1);await invoke(profile,'notifications');const coupons=page('coupons');await invoke(coupons,'onShow');assert.equal(coupons.data.items.length,3);pass('原生个人中心、消息、订单数与优惠券读取');
  await login('customer2');const orders=page('orders');await invoke(orders,'onShow');assert.equal(orders.data.orders.length,0);await login('other_store');await invoke(orders,'onShow');assert.equal(orders.data.orders.length,0);pass('原生第二顾客及第二门店不能读取第一门店订单');
  await login('customer');await invoke(product,'onLoad',{id:102});await invoke(product,'buy');const pickup=page('checkout');await invoke(pickup,'onLoad');await invoke(pickup,'submit');const pid=new URL('http://local'+lastNavigation).searchParams.get('id');const d=page('detail');await invoke(d,'onLoad',{id:pid});await invoke(d,'pay',tap({success:true}));await login('picker');await invoke(d,'accept');await invoke(d,'pick');await invoke(d,'ready');const code=d.data.o.pickup_code;
  await login('customer');const pickupHome=page('home');await invoke(pickupHome,'onShow');assert.equal(pickupHome.data.pickupOrders.length,1);assert.equal(pickupHome.data.pickupOrders[0].pickup_code,code);
  await invoke(pickupHome,'onHide');await invoke(pickupHome,'onShow');assert.equal(pickupHome.data.pickupOrders[0].id,pid);
  await login('customer2');const privateHome=page('home');await invoke(privateHome,'onShow');assert.equal(privateHome.data.pickupOrders.length,0);await invoke(privateHome,'onHide');
  await login('picker');await invoke(d,'pickup',value({code}));
  await login('customer');await invoke(pickupHome,'refreshPickup');assert.equal(pickupHome.data.pickupOrders.length,0);await invoke(pickupHome,'onHide');
  pass('首页自提提醒：备好显示、重进保留、账号隔离、核销后隐藏');assert.equal(d.data.o.state,'completed');pass('原生第二条闭环：自提下单付款、拣货、核销');
  await login('manager');await invoke(lab,'worker');assert.ok(lab.data.report.ok);const sample=await A.call('/lab/sample-order','POST',{},'native-sample-idem');const sample2=await A.call('/lab/sample-order','POST',{},'native-sample-idem');assert.equal(sample.order_id,sample2.order_id);await invoke(lab,'worker');assert.ok(lab.data.report.ok);pass('演练订单创建幂等且最终对账一致');
  await login('customer2');
  const shoppingHome=page('home'); await invoke(shoppingHome,'onShow');
  assert.equal(shoppingHome.data.shoppingCount,0);
  await Promise.all([invoke(shoppingHome,'add',tap({id:101})),invoke(shoppingHome,'add',tap({id:101})),invoke(shoppingHome,'add',tap({id:110}))]);
  assert.equal(shoppingHome.data.shoppingCount,3); assert.equal(shoppingHome.data.shoppingTotal,'30.74');
  assert.equal(shoppingHome.data.products.find(p=>p.id===101).inCart,2);
  await invoke(shoppingHome,'cartOpen');assert.equal(shoppingHome.data.shoppingOpen,true);
  await invoke(shoppingHome,'cartAdjust',tap({id:101,delta:-1}));assert.equal(shoppingHome.data.shoppingCount,2);
  pass('新增：连续加购不丢数量，卡片、底栏和展开清单实时一致');
  const secondCart=await A.call('/cart');for(const item of secondCart.items)await A.call('/cart','PUT',{sku_id:item.id,quantity:item.quantity,selected:false});
  await invoke(shoppingHome,'onShow');assert.equal(shoppingHome.data.shoppingSelected,0);assert.equal(shoppingHome.data.shoppingTotal,'0.00');
  for(const item of secondCart.items)await A.call('/cart','PUT',{sku_id:item.id,quantity:0});
  await invoke(shoppingHome,'onShow');assert.equal(shoppingHome.data.shoppingCount,0);assert.equal(shoppingHome.data.shoppingCart.length,0);
  pass('新增：全部取消勾选不能结算，删空后清单和金额复位');
  const addressCheckout=page('checkout');state.set('jm-address:'+A.pendingScope(),82);
  addressCheckout.restoreAddress([{id:81},{id:82}]);assert.equal(addressCheckout.data.addressIndex,1);
  addressCheckout.restoreAddress([{id:82}]);assert.equal(addressCheckout.data.addressIndex,0);assert.equal(addressCheckout.data.addressId,82);
  addressCheckout.restoreAddress([]);assert.equal(addressCheckout.data.addressId,null);assert.equal(addressCheckout.data.addressIndex,-1);
  const blankAddress=page('addresses');blankAddress.create();assert.equal(blankAddress.data.editing.name,'');assert.equal(blankAddress.data.editing.mobile,'');assert.equal(blankAddress.data.editing.address,'');
  pass('新增：地址按编号跨重排保留，删除后不冒用地址，新建表单留空');
  fs.writeFileSync(path.join(EVIDENCE,'native-reconciliation.json'),JSON.stringify(lab.data.report,null,2));
  fs.writeFileSync(path.join(EVIDENCE,'native-results.json'),JSON.stringify({passed:true,mode:'Node Page controller contract + live HTTP, not WeChat rendering',steps,expected_rejected_payment:true},null,2));console.log('PASS TOTAL',steps.length);
 }catch(e){fs.writeFileSync(path.join(EVIDENCE,'native-results.json'),JSON.stringify({passed:false,steps,error:e.stack},null,2));console.error(e);process.exitCode=1}
})();
