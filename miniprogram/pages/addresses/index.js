const A = require('../../utils/api');
Page(A.define({
 data:{items:[],editing:null,error:'',selecting:false,saving:false},
 onLoad(options){this.setData({selecting:options?.select==='1'});},
 async onShow(){if(A.requireLogin())this.setData({items:await A.call('/addresses'),error:''});},
 cancelEdit(){this.setData({editing:null,error:''});},
 edit(e){this.setData({editing:{...this.data.items.find(a=>a.id===Number(e.currentTarget.dataset.id))}});},
 create(){this.setData({editing:{name:'',mobile:'',address:'',latitude:31.234,longitude:121.48}});},
 choose(e){wx.setStorageSync('jm-address:'+A.pendingScope(),Number(e.currentTarget.dataset.id));wx.navigateBack();},
 async save(e){
  if(this.data.saving)return;
  const v=e.detail.value,data={name:v.name.trim(),mobile:v.mobile.trim(),address:v.address.trim(),latitude:Number(v.latitude),longitude:Number(v.longitude)};
  if(!data.name||!/^1[0-9]{10}$/.test(data.mobile)||data.address.length<4)throw new Error('请完整填写收件人、11位手机号和详细地址');
  if(v.latitude===''||v.longitude===''||!Number.isFinite(data.latitude)||!Number.isFinite(data.longitude))throw new Error('请确认演练地址坐标');
  this.setData({saving:true});
  try{const id=this.data.editing.id,saved=await A.call('/addresses'+(id?'/'+id:''),id?'PUT':'POST',data);
   wx.setStorageSync('jm-address:'+A.pendingScope(),saved.id);this.setData({editing:null});await this.onShow();
   if(this.data.selecting)wx.navigateBack();else wx.showToast({title:'地址已保存',icon:'success'});
  }finally{this.setData({saving:false});}
 },
 async remove(e){const answer=await new Promise(resolve=>wx.showModal({title:'删除地址',content:'删除后，下次配送需重新选择地址。',success:resolve,fail:()=>resolve({confirm:false})}));if(!answer.confirm)return;await A.call('/addresses/'+e.currentTarget.dataset.id,'DELETE');await this.onShow();}
}));
