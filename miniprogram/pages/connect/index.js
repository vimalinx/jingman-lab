const A = require('../../utils/api');
Page(A.define({ data: { roles: ['顾客 · 小雨', '顾客 · 第二账号', '店长', '拣货员', '配送员', '第二门店店长'], roleIndex: 0, base: A.base(), error: '' }, onLoad() { this.setData({ base: A.base() }); }, changeRole(e) { this.setData({ roleIndex: Number(e.detail.value) }); }, async submit(e) { const v = e.detail.value; if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(v.base))
        throw new Error('此实验室仅支持开发者工具本机HTTP地址'); wx.setStorageSync('jm-base', v.base); const role = ['customer', 'customer2', 'manager', 'picker', 'rider', 'other_store'][this.data.roleIndex]; await A.login(v.key, role); if (role.startsWith('customer'))
        A.go('home');
    else
        A.go(role === 'rider' ? 'rider' : 'workbench'); } }));
