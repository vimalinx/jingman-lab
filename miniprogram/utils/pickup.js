const A=require('./api');
const ready=orders=>orders.filter(o=>o.method==='pickup'&&o.state==='ready'&&o.pickup_code);
function attach(def){
 def.data={pickupOrders:[],pickupOffline:false,...def.data};
 const show=def.onShow;
 def.onShow=async function(...args){
  clearInterval(this.pickupTimer);this.pickupVisible=true;
  this.pickupScope=A.pendingScope();this.setData({pickupOrders:[],pickupOffline:false});
  if(!A.requireLogin())return;
  await this.refreshPickup();
  this.pickupTimer=setInterval(()=>this.refreshPickup(),5000);this.pickupTimer.unref?.();
  if(show)await show.apply(this,args);
 };
 for(const event of ['onHide','onUnload']){const original=def[event];def[event]=function(...args){this.pickupVisible=false;clearInterval(this.pickupTimer);if(original)return original.apply(this,args);};}
 def.refreshPickup=async function(){
  if(!this.pickupVisible||this.pickupLoading)return;
  const scope=A.pendingScope();
  if(scope!==this.pickupScope){this.setData({pickupOrders:[],pickupOffline:false});return;}
  this.pickupLoading=true;
  try{const orders=await A.call('/orders');if(this.pickupVisible&&scope===A.pendingScope())this.setData({pickupOrders:ready(orders),pickupOffline:false});}
  catch(error){if(this.pickupVisible&&scope===A.pendingScope())this.setData({pickupOffline:true});}
  finally{this.pickupLoading=false;}
 };
 def.pickupDetail=function(e){A.go('detail',e.currentTarget.dataset.id);};
 return def;
}
module.exports={ready,attach};
