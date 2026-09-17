const A = require('../../utils/api');
Page(A.define({ data: { items: [], error: '' }, async onShow() { this.setData({ items: (await A.call('/coupons')).map(c => ({ ...c, amount: A.money(c.discount_cents), threshold: A.money(c.minimum_cents) })), error: '' }); } }));
