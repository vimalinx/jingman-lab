const A = require('./api');
let queue = Promise.resolve();
async function sync(page) {
    const cart = await A.call('/cart');
    const counts = Object.fromEntries(cart.items.map(i => [i.id, i.quantity]));
    const count = cart.items.reduce((n, i) => n + i.quantity, 0);
    page.setData({ shoppingCart: cart.items.map(i => ({...A.photo(i), valid:i.valid})), shoppingCount: count,
        shoppingTotal: A.money(cart.subtotal_cents), shoppingSelected: cart.items.filter(i => i.selected && i.valid).length,
        products: (page.data.products || []).map(p => ({ ...p, inCart: counts[p.id] || 0 })) });
    if (count) wx.setTabBarBadge?.({ index: 2, text: count > 99 ? '99+' : String(count) });
    else wx.removeTabBarBadge?.({ index: 2 });
    return cart;
}
function add(page, id, delta, selected) {
    const scope = A.pendingScope();
    page.setData({ shoppingBusy: true });
    const task = queue.catch(() => {}).then(async () => {
        if (scope !== A.pendingScope()) throw new Error('身份已切换，请重新操作');
        const cart = await A.call('/cart'), old = cart.items.find(i => i.id === id);
        await A.call('/cart', 'PUT', { sku_id: id, quantity: Math.max(0, (old?.quantity || 0) + delta), selected: selected ?? true });
        await sync(page);
    });
    queue = task;
    return task.finally(() => { if (queue === task) page.setData({ shoppingBusy: false }); });
}
function attach(def) {
    def.data = { shoppingCart: [], shoppingCount: 0, shoppingSelected: 0, shoppingTotal: '0.00', shoppingOpen: false, ...def.data };
    for (const event of ['onShow', 'load']) {
        const original = def[event];
        if (event === 'load' && !original) continue;
        def[event] = async function (...args) {
            if (!A.requireLogin()) return;
            if (original) await original.apply(this, args);
            await sync(this);
        };
    }
    def.cartOpen = function () { this.setData({ shoppingOpen: true }); };
    def.cartClose = function () { this.setData({ shoppingOpen: false }); };
    def.cartNoop = function () {};
    def.cartAdjust = async function (e) {
        const id = Number(e.currentTarget.dataset.id), item = this.data.shoppingCart.find(i => i.id === id);
        await add(this, id, Number(e.currentTarget.dataset.delta), !!item?.selected);
    };
    def.cartCheckout = async function () {
        const cart = await sync(this);
        const items = cart.items.filter(i => i.selected && i.valid).map(i => ({ sku_id: i.id, quantity: i.quantity }));
        if (!items.length) throw new Error('请先在购物车勾选可售商品');
        wx.setStorageSync('jm-checkout', items); this.setData({ shoppingOpen: false }); A.go('checkout');
    };
    def.cartPage = function () { this.setData({ shoppingOpen: false }); A.go('cart'); };
    return def;
}
module.exports = { sync, add, attach };
