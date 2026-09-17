const A = require('../../utils/api');
Page(A.define({ data: { orders: [], pendingSubmission: false, error: '' }, async onShow() { if (A.requireLogin())
        await this.load(); }, async load() { this.setData({ orders: (await A.call('/orders')).map(A.order), pendingSubmission: !!A.pending(), error: '' }); }, resume() { A.go('checkout'); }, open(e) { A.go('detail', e.currentTarget.dataset.id); } }));
