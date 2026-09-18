const A = require('../../utils/api');
const C = require('../../utils/shopping');
Page(A.define({
 data:{items:[],total:'0.00',count:0,selectedCount:0,error:'',loading:true,busy:false},
 async onShow(){if(A.requireLogin())await this.load();},
 async load(){this.setData({loading:true});try{const c=await A.call('/cart');this.setData({items:c.items.map(i=>({...A.photo(i),valid:i.valid,selected:!!i.selected})),count:c.count,selectedCount:c.items.filter(i=>i.selected&&i.valid).reduce((n,i)=>n+i.quantity,0),total:A.money(c.subtotal_cents),error:''});if(c.count)wx.setTabBarBadge?.({index:2,text:String(c.count)});else wx.removeTabBarBadge?.({index:2});}finally{this.setData({loading:false});}},
 async quantity(e){if(this.data.busy)return;this.setData({busy:true});try{const id=Number(e.currentTarget.dataset.id),item=this.data.items.find(i=>i.id===id);await C.add(this,id,Number(e.currentTarget.dataset.delta),item.selected);await this.load();}finally{this.setData({busy:false});}},
 async select(e){if(this.data.busy)return;this.setData({busy:true});try{const id=Number(e.currentTarget.dataset.id),item=this.data.items.find(i=>i.id===id);await A.call('/cart','PUT',{sku_id:id,quantity:item.quantity,selected:!item.selected});await this.load();}finally{this.setData({busy:false});}},
 checkout(){const items=this.data.items.filter(i=>i.selected&&i.valid).map(i=>({sku_id:i.id,quantity:i.quantity}));if(!items.length)throw new Error('请先选择可售商品');wx.setStorageSync('jm-checkout',items);A.go('checkout');},
 shop(){A.go('home');}
}));
