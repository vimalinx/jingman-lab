const A = require('../../utils/api');
const PAGE_SIZE = 20;
Page(A.define({
    data: { items: [], q: '', page: 1, pages: 1, total: 0, editing: null,
        reasons: ['采购入库', '损耗报损', '模拟POS出库', '实物退货入库'], reasonIndex: 0, error: '', saving: false,
        fulfillment: null, channelIndex: 0, channels: ['自提和配送', '仅限自提'],
        reviewOpen: false, reviewLoading: false, reviewItems: [], reviewTotal: 0,
        sourceTotal: 0, reviewPage: 1, reviewPages: 1, loading: false,
        mockLoading: false, mockResult: null },
    async onShow() {
        if (!A.requireLogin()) return;
        await this.loadPage(this.data.page);
    },
    async loadPage(requested = 1) {
        const id = A.user().store_id || 1;
        const sequence = this.sequence = (this.sequence || 0) + 1;
        this.setData({ loading: true, error: '' });
        try {
            const result = await A.call('/catalog-page?store_id=' + id + '&page_size=' + PAGE_SIZE +
                '&page=' + requested + '&q=' + encodeURIComponent(this.data.q.trim()));
            if (sequence !== this.sequence) return;
            this.setData({ items: result.items.map(A.photo), total: result.total, page: result.page, pages: result.pages });
        } catch (error) { if (sequence === this.sequence) throw error; }
        finally { if (sequence === this.sequence) this.setData({ loading: false }); }
    },
    search(e) { if (this.data.saving) return; this.setData({ q: e.detail.value, editing: null, fulfillment: null }); this.loadPage(1); },
    async clearSearch() { if (this.data.saving) return; this.setData({ q: '', editing: null, fulfillment: null }); await this.loadPage(1); },
    async turn(e) { if (this.data.saving || this.data.loading) return; this.setData({ editing: null, fulfillment: null }); await this.loadPage(Math.max(1,this.data.page + Number(e.currentTarget.dataset.delta))); wx.pageScrollTo({ scrollTop: 0, duration: 0 }); },
    edit(e) {
        if (this.data.saving) return;
        this.adjustKey = A.key('stock');
        this.setData({ editing: this.data.items.find(p => p.id === Number(e.currentTarget.dataset.id)), fulfillment: null, reasonIndex: 0, error: '' });
        wx.pageScrollTo({ scrollTop: 0, duration: 0 });
    },
    cancelEdit() { this.setData({ editing: null, error: '' }); },
    reason(e) { this.setData({ reasonIndex: Number(e.detail.value) }); },
    async save(e) {
        if (this.data.saving || !this.data.editing) return;
        const reasons = ['purchase', 'writeoff', 'pos_sale', 'return'];
        const reason = reasons[this.data.reasonIndex], qty = Number(e.detail.value.quantity);
        if (!Number.isInteger(qty) || qty <= 0) throw new Error('数量必须是正整数');
        this.setData({ saving: true });
        try {
            await A.call('/admin/inventory/adjust', 'POST', { sku_id: this.data.editing.id,
                delta: ['writeoff', 'pos_sale'].includes(reason) ? -qty : qty, reason }, this.adjustKey);
            this.setData({ editing: null });
            await this.onShow();
        } finally { this.setData({ saving: false }); }
    },
    async toggle(e) {
        if (this.data.saving) return;
        const p = this.data.items.find(p => p.id === Number(e.currentTarget.dataset.id));
        this.setData({ saving: true });
        try {
            await A.call('/admin/products/' + p.id, 'PATCH', { version: p.version, active: !p.active });
            await this.onShow();
        } finally { this.setData({ saving: false }); }
    },
    editFulfillment(e) {
        if (this.data.saving) return;
        const p = this.data.items.find(p => p.id === Number(e.currentTarget.dataset.id));
        if (!p) return;
        this.setData({ fulfillment: p, editing: null, channelIndex: p.pickup_only ? 1 : 0, error: '' });
        wx.pageScrollTo({ scrollTop: 0, duration: 0 });
    },
    channel(e) {
        if (!this.data.saving && !this.data.fulfillment?.fulfillment_note)
            this.setData({ channelIndex: Number(e.detail.value) });
    },
    cancelFulfillment() {
        if (!this.data.saving) this.setData({ fulfillment: null, error: '' });
    },
    async saveFulfillment(e) {
        if (this.data.saving || !this.data.fulfillment) return;
        const p = this.data.fulfillment;
        const raw = String(e.detail.value.weight || '').trim();
        const weight = raw === '' ? null : Number(raw);
        if (weight !== null && (!Number.isInteger(weight) || weight < 1 || weight > 1000000))
            throw new Error('重量须为1至1000000克的整数；未确认请留空');
        this.setData({ saving: true, error: '' });
        try {
            await A.call('/admin/products/' + p.id + '/fulfillment', 'PATCH', {
                version: p.version, weight_g: weight,
                pickup_only: !!p.fulfillment_note || this.data.channelIndex === 1
            });
            this.setData({ fulfillment: null });
            await this.onShow();
            wx.showToast({ title: '履约资料已保存', icon: 'success' });
        } catch (error) {
            if (error.code === 'version_conflict') {
                this.setData({ fulfillment: null });
                await this.onShow();
            }
            throw error;
        } finally { this.setData({ saving: false }); }
    },
    async openReview() {
        if (this.data.reviewLoading) return;
        this.setData({ reviewLoading: true, reviewOpen: false, error: '' });
        try {
            const records = await A.call('/admin/import-review');
            this.reviewRecords = records.map(r => ({ ...r, issues: JSON.parse(r.review_json).join('；') }))
                .filter(r => r.issues);
            this.setData({ reviewOpen: true, sourceTotal: records.length });
            this.renderReview(1);
            wx.pageScrollTo({ scrollTop: 0, duration: 0 });
        } finally { this.setData({ reviewLoading: false }); }
    },
    renderReview(requested) {
        const records = this.reviewRecords || [];
        const pages = Math.max(1, Math.ceil(records.length / PAGE_SIZE));
        const page = Math.max(1, Math.min(pages, requested));
        this.setData({ reviewItems: records.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
            reviewTotal: records.length, reviewPage: page, reviewPages: pages });
    },
    turnReview(e) {
        this.renderReview(this.data.reviewPage + Number(e.currentTarget.dataset.delta));
        wx.pageScrollTo({ scrollTop: 0, duration: 0 });
    },
    closeReview() {
        this.setData({ reviewOpen: false });
    },
    async queryMock(e) {
        if (this.data.mockLoading) return;
        const barcode = String(e.detail.value.barcode || '').trim();
        if (!/^[0-9]{8,14}$/.test(barcode)) throw new Error('请输入8至14位条码；模拟样例为9900000000001');
        this.setData({ mockLoading: true, mockResult: null, error: '' });
        try {
            const result = await A.call('/admin/lakala-mock/query', 'POST', { barcode });
            if (!result.mock || !result.verified) throw new Error('没有获得已验签的模拟响应');
            this.setData({ mockResult: { count: result.data.saleProduct.length,
                items: result.data.saleProduct.map(p => ({ ...p, price: A.money(p.unitPrice) })) } });
        } finally { this.setData({ mockLoading: false }); }
    }
}));
