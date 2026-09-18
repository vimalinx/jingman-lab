const A = require('../../utils/api');
Page(A.define({
    data: { method: 'pickup', store: {}, addresses: [], addressIndex: 0, addressId: null, previewItems: [],
        coupons: [{ id: null, title: '不使用优惠券' }], couponIndex: 0, quote: null, error: '', submitting: false, pendingSubmission: false },
    async onLoad() {
        if (!A.requireLogin()) return;
        this.pendingScope = A.pendingScope();
        const saved = A.pending(this.pendingScope);
        if (saved) {
            this.restoreOnly = true;
            this.pendingOrder = saved;
            this.items = saved.items || [];
            this.setData({ pendingSubmission: true, method: saved.method || 'pickup', quote: null });
            this.initialized = true;
            return;
        }
        this.items = wx.getStorageSync('jm-checkout') || [];
        if (!this.items.length) throw new Error('没有结算商品');
        const [addresses, coupons, store] = await Promise.all([A.call('/addresses'), A.call('/coupons'), A.call('/store')]);
        this.setData({ addresses, store, coupons: [{ id: null, title: '不使用优惠券' }, ...coupons.filter(c => c.state === 'available' && !c.expired)] });
        this.restoreAddress(addresses);
        const products = await A.call('/products');
        this.setData({ previewItems: this.items.map(i => ({ ...A.photo(products.find(p => p.id === i.sku_id) || {}), quantity:i.quantity })) });
        this.initialized = true;
        await this.refresh();
    },
    async onShow() {
        if (this.initialized && !this.data.pendingSubmission && !this.completedOrder) {
            const addresses = await A.call('/addresses');
            this.setData({ addresses, store: await A.call('/store') });
            this.restoreAddress(addresses);
            await this.refresh();
        }
    },
    restoreAddress(addresses) {
        const key = 'jm-address:' + A.pendingScope();
        const id = wx.getStorageSync(key) || this.data.addressId;
        const index = id ? addresses.findIndex(a => a.id === id) : (addresses.length ? 0 : -1);
        this.setData({ addressIndex:index, addressId:addresses[index]?.id || null });
        if (index < 0) wx.removeStorageSync(key);
    },
    async refresh() {
        if (this.data.submitting || this.data.pendingSubmission || this.completedOrder) return;
        const sequence = this.sequence = (this.sequence || 0) + 1;
        this.setData({ quote: null, error: '' });
        if (this.restoreOnly) {
            const [addresses, coupons, store] = await Promise.all([A.call('/addresses'), A.call('/coupons'), A.call('/store')]);
            if (sequence !== this.sequence) return;
            this.setData({ addresses, store, coupons: [{ id: null, title: '不使用优惠券' }, ...coupons.filter(c => c.state === 'available' && !c.expired)] });
            this.restoreOnly = false;
        }
        if (this.data.method === 'delivery' && !this.data.addresses[this.data.addressIndex]) { this.setData({error:'请先添加或选择收货地址，再确认配送费用'}); return; }
        let q;
        try {
            q = await A.call('/quotes', 'POST', { store_id: 1, method: this.data.method, items: this.items,
                address_id: this.data.method === 'delivery' ? (this.data.addresses[this.data.addressIndex]?.id || null) : null,
                coupon_id: this.data.coupons[this.data.couponIndex]?.id || null });
        } catch (error) {
            if (sequence !== this.sequence) return;
            throw error;
        }
        if (sequence !== this.sequence) return;
        this.quoteId = q.id; this.submitKey = A.key('checkout');
        this.setData({ quote: { ...q, total: A.money(q.total_cents), subtotal: A.money(q.subtotal_cents),
            discount: A.money(q.discount_cents), shipping: A.money(q.shipping_cents), items: q.items.map(A.photo),
            weight: q.shipping_detail?.weight_g == null ? '待确认' : q.shipping_detail.weight_g / 1000 + '千克',
            baseShipping: A.money(q.shipping_detail?.base_cents || 0), extraShipping: A.money(q.shipping_detail?.extra_weight_cents || 0) } });
    },
    async method(e) { if (this.data.submitting || this.data.pendingSubmission) return; this.setData({ method: e.currentTarget.dataset.method }); await this.refresh(); },
    async address(e) { if (this.data.submitting || this.data.pendingSubmission) return; const index=Number(e.detail.value); this.setData({ addressIndex:index, addressId:this.data.addresses[index]?.id }); wx.setStorageSync('jm-address:' + A.pendingScope(),this.data.addressId); await this.refresh(); },
    async coupon(e) { if (this.data.submitting || this.data.pendingSubmission) return; this.setData({ couponIndex: Number(e.detail.value) }); await this.refresh(); },
    async submit() {
        if (this.data.submitting || this.completedOrder || (!this.data.quote && !this.pendingOrder)) return;
        if (this.pendingScope !== A.pendingScope()) throw new Error('身份或服务已切换，请重新进入结算');
        // Persist BEFORE requesting: a killed page/app can resume the same attempt.
        this.pendingOrder = A.pending(this.pendingScope) || this.pendingOrder || {
            quote_id: this.quoteId, key: this.submitKey, items: this.items, method: this.data.method
        };
        A.savePending(this.pendingOrder, this.pendingScope);
        this.setData({ submitting: true, error: '' });
        try {
            const o = await A.call('/orders', 'POST', { quote_id: this.pendingOrder.quote_id }, this.pendingOrder.key);
            A.clearPending(this.pendingOrder.key, this.pendingScope);
            this.completedOrder = o.id;
            this.pendingOrder = null;
            this.setData({ pendingSubmission: false, quote: null });
            wx.removeStorageSync('jm-checkout'); A.go('detail', o.id);
        } catch (error) {
            const rejected = ['quote_expired', 'quote_changed', 'closed', 'inactive', 'sold_out',
                'stock_conflict', 'review_required', 'coupon_unavailable', 'coupon_minimum',
                'delivery_hours', 'pickup_only', 'weight_required', 'delivery_unconfirmed',
                'address_required', 'out_of_range', 'minimum_order'];
            if (rejected.includes(error.code)) {
                A.clearPending(this.pendingOrder.key, this.pendingScope);
                this.pendingOrder = null;
                this.setData({ pendingSubmission: false, quote: null });
            } else {
                this.setData({ pendingSubmission: true });
            }
            throw error;
        } finally { this.setData({ submitting: false }); }
    },
    orders() { A.go('orders'); },
    addresses() { if (!this.data.submitting && !this.data.pendingSubmission) wx.navigateTo({url:'/pages/addresses/index?select=1'}); }
}));
