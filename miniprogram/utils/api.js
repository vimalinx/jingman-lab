const config = require('../config');
const fmt = require('./format');
function base() { return wx.getStorageSync('jm-base') || config.baseURL; }
let redirecting = false;
function enterLogin() {
    if (redirecting) return;
    redirecting = true;
    wx.reLaunch({ url: '/pages/connect/index', complete: () => { redirecting = false; } });
}
function call(path, method = 'GET', data, key) {
    const requestBase = base();
    const header = {};
    const token = wx.getStorageSync('jm-token');
    if (token)
        header.Authorization = 'Bearer ' + token;
    if (data !== undefined)
        header['Content-Type'] = 'application/json';
    if (key)
        header['Idempotency-Key'] = key;
    return new Promise((resolve, reject) => wx.request({ url: requestBase + '/api' + path, method, data, header, timeout: 15000, success: r => {
        if (path !== '/session' && (requestBase !== base() || token !== wx.getStorageSync('jm-token'))) {
            const stale = new Error('登录身份或服务已切换，请重新进入页面');
            stale.code = 'session_changed'; reject(stale); return;
        }
        if (r.statusCode >= 200 && r.statusCode < 300)
            resolve(r.data);
        else {
            const e = new Error(r.data?.error?.message || '请求失败（HTTP ' + r.statusCode + '）');
            e.code = r.data?.error?.code;
            e.status = r.statusCode;
            // Ignore late 401s from a previous account or server.
            if (r.statusCode === 401 && path !== '/session' &&
                token === wx.getStorageSync('jm-token') && requestBase === base()) {
                wx.removeStorageSync('jm-token');
                wx.removeStorageSync('jm-user');
                wx.removeStorageSync('jm-checkout');
                enterLogin();
            }
            reject(e);
        } }, fail: r => reject(new Error('本机联调连接失败。请先启动后端，检查开发者工具的域名校验设置。' + (r.errMsg || ''))) }));
}
function key(p = 'mp') { return p + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12); }
let loginSequence = 0;
async function login(access_key, persona) {
    const sequence = ++loginSequence, loginBase = base();
    const r = await call('/session', 'POST', { access_key, persona });
    if (sequence !== loginSequence || loginBase !== base()) throw new Error('登录请求已失效，请重新进入');
    wx.removeStorageSync('jm-checkout');
    wx.setStorageSync('jm-token', r.token); wx.setStorageSync('jm-user', r.user); return r;
}
function requireLogin() { if (!wx.getStorageSync('jm-token')) {
    enterLogin();
    return false;
} return true; }
function user() { return wx.getStorageSync('jm-user') || {}; }
function pendingScope() { return 'jm-pending-order:' + encodeURIComponent(base()) + ':' + user().id; }
function pending(scope = pendingScope()) { return wx.getStorageSync(scope) || null; }
function savePending(value, scope = pendingScope()) {
    if (!user().id || !value.quote_id || !value.key) throw new Error('无法保存待确认订单，请重新登录');
    wx.setStorageSync(scope, value);
    if (pending(scope)?.key !== value.key) throw new Error('待确认订单保存失败，尚未发起下单');
    return value;
}
function clearPending(key, scope = pendingScope()) {
    if (pending(scope)?.key === key) wx.removeStorageSync(scope);
}
const photo = p => ({ ...p, imageURL: base() + '/assets/' + p.image + '.webp', price: fmt.money(p.price_cents), oldPrice: p.old_price_cents ? fmt.money(p.old_price_cents) : '', valid: p.active !== 0 && p.available > 0 });
function order(o) { return { ...o, label: fmt.states[o.state], weight: o.shipping_detail?.weight_g == null ? "待确认" : o.shipping_detail.weight_g / 1000 + "千克", baseShipping: fmt.money(o.shipping_detail?.base_cents || 0), extraShipping: fmt.money(o.shipping_detail?.extra_weight_cents || 0), shipping: fmt.money(o.shipping_cents), total: fmt.money(o.total_cents), paid: fmt.money(o.paid_cents), refunded: fmt.money(o.refunded_cents), items: o.items.map(l => ({ ...l, imageURL: base() + '/assets/' + l.image + '.webp', net: fmt.money(l.net_cents), remaining: l.quantity - l.shortage_qty })), refunds: o.refunds.map(r => ({ ...r, amount: fmt.money(r.amount_cents) })), timeline: o.timeline.map(t => ({ ...t, label: fmt.events[t.action] || t.action })), address: { ...o.address, mobile: o.address.mobile ? fmt.phoneEncryption(o.address.mobile) : '' } }; }
function define(def) {
    for (const name of Object.keys(def)) {
        if (typeof def[name] === 'function') {
            const fn = def[name];
            def[name] = function (...args) {
                const fail = e => {
                    this.setData({ error: e.message });
                    wx.showToast({ title: e.message, icon: 'none', duration: 3500 });
                    return { failed: true, error: e };
                };
                try {
                    // Input handlers must keep their synchronous return value.
                    const result = fn.apply(this, args);
                    return result && typeof result.then === 'function'
                        ? Promise.resolve(result).catch(fail) : result;
                }
                catch (e) {
                    return fail(e);
                }
            };
        }
    }
    return def;
}
function go(page, id) { const url = '/pages/' + page + '/index' + (id ? '?id=' + encodeURIComponent(id) : ''); if (['home', 'category', 'cart', 'profile'].includes(page))
    wx.switchTab({ url });
else
    wx.navigateTo({ url }); }
module.exports = { call, key, login, requireLogin, user, photo, order, define, go, base,
    pendingScope, pending, savePending, clearPending, ...fmt };
