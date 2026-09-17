const A = require('../../utils/api');
Page(A.define({ data: { d: null, user: {}, error: '' }, async onShow() { const d = await A.call('/admin/dashboard'); this.setData({ d: { ...d, net: A.money(d.net_cents) }, user: A.user(), error: '' }); }, go(e) { A.go(e.currentTarget.dataset.page); }, connect() { wx.reLaunch({ url: '/pages/connect/index' }); } }));
