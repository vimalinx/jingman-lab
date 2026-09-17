const A = require('../../utils/api');
Page(A.define({ data: { categories: [], products: [], page: 1, pages: 1, total: 0, loading: false, q: '', cat: 0, error: '' }, async onShow() { if (!A.requireLogin())
        return; const keys = wx.getStorageInfoSync().keys;
        if (keys.includes('jm-category')) { this.setData({ cat: Number(wx.getStorageSync('jm-category')) || 0 }); wx.removeStorageSync('jm-category'); }
        if (keys.includes('jm-search')) { this.setData({ q: wx.getStorageSync('jm-search') || '' }); wx.removeStorageSync('jm-search'); } this.setData({ categories: await A.call('/categories') }); await this.load(); }, async load(requested = 1) {
        const sequence = this.sequence = (this.sequence || 0) + 1;
        this.setData({ loading: true, error: '' });
        try {
            const result = await A.call('/catalog-page?page_size=24&page=' + Math.max(1,requested) +
                '&q=' + encodeURIComponent(this.data.q) + (this.data.cat ? '&category_id=' + this.data.cat : ''));
            if (sequence !== this.sequence) return;
            this.setData({ products: result.items.map(A.photo), total: result.total, page: result.page, pages: result.pages });
        } catch(error) { if (sequence === this.sequence) throw error; }
        finally { if (sequence === this.sequence) this.setData({ loading: false }); }
    }, async turn(e) { if (this.data.loading) return; await this.load(this.data.page + Number(e.currentTarget.dataset.delta)); wx.pageScrollTo({ scrollTop: 0, duration: 0 }); }, async search(e) { this.setData({ q: e.detail.value }); await this.load(); }, async select(e) { this.setData({ cat: Number(e.currentTarget.dataset.id) }); await this.load(); }, detail(e) { A.go('product', e.currentTarget.dataset.id); }, async add(e) { const sku = Number(e.currentTarget.dataset.id), cart = await A.call('/cart'), old = cart.items.find(i => i.id === sku); await A.call('/cart', 'PUT', { sku_id: sku, quantity: (old?.quantity || 0) + 1 }); wx.showToast({ title: '已加入', icon: 'success' }); } }));
