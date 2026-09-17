/* Jingman integration UI. No remote scripts, analytics, external images or fake counters. */
'use strict';
const { money, yuanToFen, phoneEncryption, states, events } = Jingman;
const root = document.querySelector('#app'), overlay = document.querySelector('#overlay');
const S = { key: sessionStorage.getItem('jm-key') || '', token: sessionStorage.getItem('jm-token') || '', user: JSON.parse(sessionStorage.getItem('jm-user') || 'null'), persona: sessionStorage.getItem('jm-persona') || 'customer', products: [], categories: [], store: null, cart: { items: [], count: 0, subtotal_cents: 0 }, quantity: 1, checkout: JSON.parse(sessionStorage.getItem('jm-checkout') || 'null'), method: 'pickup', couponId: null, addressId: null, quote: null, quoteError: '', checkoutKey: null, sequence: 0, rendering: false, pending: 0, viewData: null };
const paths = { home: 'M3 11 12 3l9 8v10h-6v-7H9v7H3Z', grid: 'M3 3h7v7H3Zm11 0h7v7h-7ZM3 14h7v7H3Zm11 0h7v7h-7Z', cart: 'M2 3h3l3 13h11l3-10H6M9 21h.01M18 21h.01', user: 'M20 21v-2a8 8 0 0 0-16 0v2M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z', search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z', arrow: 'm9 5 7 7-7 7', back: 'm15 5-7 7 7 7', plus: 'M12 5v14M5 12h14', check: 'm5 12 4 4L19 6', pin: 'M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0ZM15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z', leaf: 'M20 3C7 3 3 10 6 16c5 7 16 3 14-13ZM3 22 16 8', truck: 'M1 5h13v12H1Zm13 5h5l4 5v2h-9M8 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm13 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z', bag: 'M4 7h16l1 14H3ZM8 7V5a4 4 0 0 1 8 0v2', box: 'm3 7 9-5 9 5v12l-9 4-9-4Zm0 0 9 5 9-5M12 12v11M7 5l10 5', clock: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0ZM12 6v6l4 3', ticket: 'M3 4h18v6a2 2 0 0 0 0 4v6H3v-6a2 2 0 0 0 0-4ZM9 4v3m0 3v4m0 3v3', store: 'M3 3h18l2 6a4 4 0 0 1-6 3 4 4 0 0 1-5 0 4 4 0 0 1-5 0A4 4 0 0 1 1 9Zm0 10v9h18v-9M9 22v-7h6v7', chart: 'M3 21h18M5 17V9h3v8m3 0V3h3v14m3 0v-6h3v6', shield: 'm12 2 9 4v7c0 5-9 9-9 9S3 18 3 13V6Zm-5 10 3 3 7-7', bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 8-3 8h18s-3-1-3-8M10 21h4', refresh: 'M20 7a9 9 0 0 0-15-3L2 7m0-5v5h5m-3 10a9 9 0 0 0 15 3l3-3m0 5v-5h-5', heart: 'M20 4c-3-3-7-1-8 2-1-3-5-5-8-2-5 5 1 11 8 17 7-6 13-12 8-17Z', close: 'm6 6 12 12M6 18 18 6', settings: 'M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0Z', print: 'M6 8V2h12v6M6 18H2V8h20v10h-4M6 14h12v8H6ZM18 11h1', code: 'm8 5-7 7 7 7m8-14 7 7-7 7M14 2l-4 20', file: 'M5 2h10l4 4v16H5ZM9 10h6m-6 4h6m-6 4h4', headset: 'M3 13v-3a9 9 0 0 1 18 0v3M3 12h4v8H3Zm14 0h4v8h-4ZM20 20c0 3-5 3-7 3', wallet: 'M20 6H3a2 2 0 0 1 0-4h15v4M3 6v15h19V7M16 11h6v6h-6ZM18 14h.01' };
const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.box}"/></svg>`;
const e = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const amount = c => `<span class="price"><small>¥</small>${money(c || 0)}</span>`;
const image = (key, cls = '', alt = '') => `<img class="${cls}" src="/assets/${e(key)}.webp" alt="${e(alt)}" loading="lazy">`;
const fulfillmentBadge = p => p.pickup_only ? '<span class="pill amber">仅限自提</span>' : '';
function deliveryTerms() {
    const r = S.store?.delivery_rules;
    if (!r) return '';
    const rounding = r.rounding === 'proportional' ? '超出部分按实际重量比例计费' : '超出部分不足1千克按1千克计费';
    return `<p class="footnote">配送 ${e(r.start)}–${e(r.end)}${r.provisional_hours ? '（暂定）' : ''}；${r.included_weight_g / 1000}千克内按基础运费，超出每千克加¥${money(r.extra_step_cents)}。${rounding}${r.provisional_rounding ? '（零头规则待确认）' : ''}。满额免基础运费，超重费另计。每单最多使用1张优惠券；散装零食和槟榔仅限自提。</p>`;
}
function shippingBreakdown(detail, method) {
    if (!detail?.rules || method !== 'delivery') return '';
    return `<div class="bill-line"><span>配送总重量</span><b>${detail.weight_g == null ? '待确认' : detail.weight_g / 1000 + '千克'}</b></div><div class="bill-line"><span>基础配送费</span><b>¥${money(detail.base_cents)}</b></div><div class="bill-line"><span>超重附加费</span><b>¥${money(detail.extra_weight_cents)}</b></div>`;
}
const timeLabel = t => new Date(t * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
const uniqueKey = prefix => prefix + '-' + (crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(16)), x => x.toString(16).padStart(2, '0')).join(''));
const isCustomer = () => S.user?.role === 'customer';
const isManager = () => S.user?.role === 'manager';
const isOperator = () => S.user?.id === 10;
const route = () => { const hash = location.hash.slice(1) || '/home'; const [path, query = ''] = hash.split('?'); return { page: path.slice(1) || 'home', query: new URLSearchParams(query) }; };
function go(page, params = {}) { const hash = '#/' + page + (Object.keys(params).length ? '?' + new URLSearchParams(params) : ''); if (location.hash === hash)
    render();
else
    location.hash = hash; window.scrollTo(0, 0); }
let toastTimer;
function toast(message) { const el = document.querySelector('#toast'); el.textContent = message; el.classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('visible'), 4200); }
async function api(path, method = 'GET', body, key) {
    const headers = {};
    if (S.token)
        headers.Authorization = 'Bearer ' + S.token;
    if (body !== undefined)
        headers['Content-Type'] = 'application/json';
    if (key)
        headers['Idempotency-Key'] = key;
    const response = await fetch('/api' + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) {
        const error = new Error(data.error?.message || data.detail || '请求没有完成，请重试');
        error.code = data.error?.code;
        error.status = response.status;
        throw error;
    }
    return data;
}
async function login(persona = S.persona) {
    const result = await api('/session', 'POST', { access_key: S.key, persona });
    S.token = result.token;
    S.user = result.user;
    S.persona = persona;
    for (const [k, v] of Object.entries({ 'jm-key': S.key, 'jm-token': S.token, 'jm-user': JSON.stringify(S.user), 'jm-persona': persona }))
        sessionStorage.setItem(k, v);
}
async function globals() {
    [S.products, S.categories, S.store] = await Promise.all([api('/products?store_id=' + (S.user?.store_id || 1)), api('/categories'), api('/store?store_id=' + (S.user?.store_id || 1))]);
    S.cart = isCustomer() ? await api('/cart') : { items: [], count: 0, subtotal_cents: 0 };
}
function navItems() {
    if (isCustomer())
        return [['home', 'home', '首页'], ['categories', 'grid', '商品分类'], ['cart', 'cart', '购物车'], ['orders', 'file', '我的订单'], ['profile', 'user', '个人中心']];
    if (S.user.role === 'rider')
        return [['rider', 'truck', '配送任务'], ['dashboard', 'chart', '门店概览']];
    const items = [['dashboard', 'chart', '经营概览'], ['orders', 'file', '订单履约']];
    if (isManager())
        items.push(['inventory', 'box', '商品与库存'], ['marketing', 'ticket', '会员与营销'], ['settings', 'settings', '门店设置']);
    if (isOperator())
        items.push(['lab', 'code', '联调实验室']);
    return items;
}
function brand() { return `<button class="brand" data-action="shop" aria-label="京漫便民首页"><img src="/assets/leaf.svg" alt=""><div><div class="brand-title">京漫便民</div><small>JINGMAN · FRESH DAILY</small></div></button>`; }
function shell(content, page) {
    const nav = navItems();
    const active = page === 'order' ? 'orders' : page === 'product' ? 'categories' : page;
    const roleOptions = [['customer', '顾客 · 本地预览'], ['customer2', '顾客 · 第二账号'], ['manager', '店长工作台'], ['picker', '拣货员视角'], ['rider', '配送员视角'], ['other_store', '二号店 · 权限测试']].filter(([v]) => !S.store?.local_preview || v !== 'other_store').map(([v, l]) => `<option value="${v}" ${S.persona === v ? 'selected' : ''}>${l}</option>`).join('');
    return `<header class="header"><div class="header-inner">${brand()}<nav class="top-links" aria-label="工作区"><a href="#/home" data-action="shop" class="${isCustomer() ? 'current' : ''}">在线超市</a><a href="#/dashboard" data-action="work" class="${!isCustomer() && page !== 'lab' ? 'current' : ''}">门店工作台</a><a href="#/lab" data-action="lab" class="${page === 'lab' ? 'current' : ''}">联调实验室</a></nav><span class="pill amber header-lab"><span class="dot"></span>本地演练 · 不真实扣款</span><select class="persona" aria-label="切换演练身份" data-change="persona">${roleOptions}</select></div></header>
 <div class="layout"><aside class="sidebar"><div class="store-tile"><div class="row">${icon('store')}<b>${e(S.store.name)}</b></div><p><span class="green">${S.store.open ? '● 营业中' : '● 已打烊'}</span> · 模拟门店</p><p>${S.store.local_preview ? '园区配送待确认 / 支持自提' : S.store.radius_km + 'km 配送范围 / 支持自提'}</p></div><nav class="side-menu" aria-label="侧栏">${nav.map(([p, i, l]) => `<a href="#/${p}" class="${active === p ? 'active' : ''}">${icon(i)}${l}${p === 'cart' && S.cart.count ? `<span class="badge">${S.cart.count}</span>` : ''}</a>`).join('')}</nav><div class="side-note">新鲜好物，健康每一天。<br>真实数据流 · 模拟外部服务<br><span class="green">● SQLite 已连接</span></div></aside><main class="main" id="main">${content}<footer class="footer">JINGMAN · 京漫便民本地联调实验室<br>${S.store.local_preview ? '门店商品快照 · 支付、配送、打印为本地演练' : '商品图片与地址为演练资料，支付 / 配送 / 打印均不连接真实服务。'}</footer></main></div>
 <nav class="bottom-nav" aria-label="底部导航">${(isCustomer() ? [nav[0], nav[1], nav[2], nav[4]] : nav.slice(0, 4)).map(([p, i, l]) => `<a href="#/${p}" class="${active === p ? 'active' : ''}">${icon(i)}<span>${p === 'categories' ? '分类' : p === 'profile' ? '我的' : l}</span>${p === 'cart' && S.cart.count ? `<span class="badge">${S.cart.count}</span>` : ''}</a>`).join('')}</nav>`;
}
function head(title, subtitle = '', actions = '', eyebrow = 'JINGMAN / NEIGHBORHOOD MARKET') { return `<div class="page-head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1>${subtitle ? `<p class="subtitle">${subtitle}</p>` : ''}</div>${actions}</div>`; }
function button(label, action, cls = 'primary', attrs = '') { return `<button class="button ${cls}" data-action="${action}" ${attrs}>${label}</button>`; }
function empty(title, message, buttonHtml = '') { return `<div class="empty">${icon('bag')}<h3>${title}</h3><p>${message}</p>${buttonHtml}</div>`; }
function searchForm(query = '', target = 'categories') { return `<form class="search" data-form="search" data-target="${target}">${icon('search')}<input type="search" name="q" value="${e(query)}" placeholder="搜索商品，例如：香蕉、牛奶、草莓" aria-label="搜索商品"><button aria-label="开始搜索">${icon('arrow')}</button></form>`; }
function productCard(p, list = false) {
    const disabled = !p.active || p.available <= 0;
    return `<article class="${list ? 'list-product' : 'product-card'}" data-sku="${p.id}">${!list && disabled ? '<span class="sold">已售罄</span>' : ''}<a href="#/product?id=${p.id}" aria-label="查看${e(p.name)}">${image(p.image, list ? '' : 'product-photo', p.name)}</a><div class="product-info">${p.pickup_only ? fulfillmentBadge(p) : `<span class="product-tag">${e(p.tag)}</span>`}<a href="#/product?id=${p.id}"><h3>${e(p.name)}</h3></a><p class="muted">${e(p.unit)}${list ? ' · 门店直供' : ''}</p><div class="row spread"><div>${amount(p.price_cents)}${p.old_price_cents > p.price_cents ? `<span class="old-price">¥${money(p.old_price_cents)}</span>` : ''}</div><button class="add" data-action="add" data-id="${p.id}" aria-label="添加${e(p.name)}" ${disabled ? 'disabled' : ''}>${icon('plus')}</button></div></div></article>`;
}
function home() {
    const catImages = { 1: 'lettuce', 2: 'milk', 3: 'cola', 4: 'snack', 5: 'oil', 6: 'daily' };
    const featured = S.products.filter(p => p.active && p.available > 0).slice(0, 12);
    return `${head('今天，也要好好生活。', '从家门口的好食材开始。', `<span class="pill header-status"><span class="dot"></span>${S.store.open ? '门店营业中' : '门店已打烊'}</span>`)}${searchForm()}
 <section class="hero"><img class="hero-image" src="/assets/hero.webp" alt="木箱里的新鲜蔬菜"><div class="hero-copy"><div class="eyebrow">FRESH PICKS, EVERY DAY</div><h1>新鲜的日常，<br>就在你身边。</h1><p>当季好食材 · 门店精心选 · 把新鲜带回家</p><a class="button" href="#/categories">去逛一逛 ${icon('arrow')}</a></div></section>
 ${S.store.local_preview ? `<section class="card"><h3>${e(S.store.name)}</h3><p>${e(S.store.address)}</p><p>营业时间 ${e(S.store.hours)} · 客服 ${e(S.store.phone)}</p><p class="footnote">${e(S.store.delivery_rules ? String(S.store.notice || '').replace('免配送费', '免基础配送费（超重费另计）') : S.store.notice)}</p><p>到店自提可用；园区配送边界待确认。</p>${deliveryTerms()}</section>` : ''}
 <div class="benefits"><span>${icon('leaf')}当季新鲜好物</span><span>${icon('shield')}品质用心挑选</span><span>${icon('truck')}门店配送 / 自提</span></div>
 <div class="categories">${S.categories.slice(0, 6).map(c => `<a class="category" href="#/categories?cat=${c.id}">${S.store.local_preview ? icon('bag') : image(catImages[c.id] || 'daily', '', c.name)}${e(c.name)}</a>`).join('')}</div>
 <div class="section-title"><h2>今日推荐</h2><a href="#/categories"><small>把新鲜装进购物车 ${icon('arrow')}</small></a></div><div class="product-grid">${featured.map(p => productCard(p)).join('')}</div>`;
}
function categories(q) {
    const category = Number(q.get('cat') || 0), keyword = q.get('q') || '';
    const products = S.products.filter(p => (!category || p.category_id === category) && (!keyword || p.name.includes(keyword) || p.barcode === keyword));
    return `${head('商品分类', '一日三餐，生活所需，都在这里。')}${searchForm(keyword)}<div class="category-layout" style="margin-top:22px"><nav class="category-menu"><a class="${!category ? 'active' : ''}" href="#/categories">全部商品</a>${S.categories.map(c => `<a class="${category === c.id ? 'active' : ''}" href="#/categories?cat=${c.id}">${e(c.name)}</a>`).join('')}</nav><div><div class="chips"><span class="chip active">${keyword ? '搜索结果' : '门店好物'} · ${products.length}</span><span class="chip">可售库存实时读取</span></div><div class="stack">${products.length ? products.map(p => productCard(p, true)).join('') : empty('没有找到这件好物', '换个关键词试试看。')}</div></div></div>`;
}
async function detail(q) {
    const p = await api('/products/' + Number(q.get('id') || 103));
    S.viewData = p;
    const favorites = isCustomer() ? await api('/favorites') : [];
    return `<a class="breadcrumb" href="#/home">${icon('back')}返回超市 / 商品详情</a><div class="detail-grid"><img class="detail-photo" src="/assets/${p.family === 'strawberry' ? 'strawberry-detail' : e(p.image)}.webp" alt="${e(p.name)}"><section class="card detail-panel">${p.pickup_only ? fulfillmentBadge(p) : `<span class="product-tag">${e(p.tag)}</span>`}<h1>${e(p.name)}</h1><p>${e(p.description)}</p><div>${amount(p.price_cents)}${p.old_price_cents > p.price_cents ? `<span class="old-price">¥${money(p.old_price_cents)}</span>` : ''}</div><div class="variants">${p.variants.map(v => `<button class="variant ${v.id === p.id ? 'active' : ''}" data-action="variant" data-id="${v.id}">${e(v.unit)}</button>`).join('')}</div><div class="row spread"><span class="muted">购买数量</span><div class="stepper"><button data-action="quantity-minus" aria-label="减少商品数量" ${S.quantity <= 1 ? 'disabled' : ''}>−</button><output>${S.quantity}</output><button data-action="quantity-plus" aria-label="增加商品数量" ${S.quantity >= p.available ? 'disabled' : ''}>+</button></div></div><div class="detail-service row spread"><span>${icon('truck')} ${p.pickup_only ? "仅限自提 · 不收配送费" : "自提免费 / 满" + money(S.store.free_shipping_cents) + (S.store.delivery_rules ? "免基础配送费，超重另计" : "免配送费")}</span><span class="green">${p.active && p.available > 0 ? '库存 ' + p.available + ' 份' : '暂时售罄'}</span></div><div class="detail-actions">${button('加入购物车', 'add', 'secondary', `data-id="${p.id}" data-quantity="${S.quantity}" ${!p.active || !p.available ? 'disabled' : ''}`)}${button('立即购买', 'buy-now', 'primary', `data-id="${p.id}" ${!p.active || !p.available ? 'disabled' : ''}`)}</div><button class="text-button" data-action="favorite" data-id="${p.id}">${icon('heart')} ${favorites.includes(p.id) ? '已收藏' : '收藏好物'}</button></section></div><section class="card" style="margin-top:23px"><h3>关于这份新鲜</h3><p class="subtitle">${e(p.description)}</p><p class="footnote" style="margin-top:15px">${S.store.local_preview ? '称重及异常商品暂不可下单。门店资料为导出快照，结算以服务端核价为准。' : '固定规格演练商品，创建订单时服务端再次核价。'}</p></section>`;
}
function cartView() {
    const items = S.cart.items;
    const valid = items.filter(i => i.selected && i.valid), remaining = Math.max(0, S.store.free_shipping_cents - S.cart.subtotal_cents);
    if (!items.length)
        return `${head('购物车', '把今天需要的好物，一起带回家。')}${empty('购物车还空着', '去挑一点新鲜，给今天添点好心情。', '<a class="button primary" href="#/home">去逛一逛</a>')}`;
    return `${head('购物车', `${items.length} 种好物 · 价格与库存以门店为准`)}<div class="shipping-hint">${icon('truck')}${remaining ? '商品还差 ¥' + money(remaining) + ' 达到免基础配送费门槛' : '商品金额已达免基础配送费门槛'}<span class="muted">（优惠后计算${S.store.delivery_rules ? "，超重费另计" : ""}）</span></div><div class="cart-layout"><div class="stack">${items.map(i => `<article class="cart-item ${i.valid ? '' : 'invalid'}"><input class="check" type="checkbox" data-change="cart-select" data-id="${i.id}" aria-label="选择${e(i.name)}" ${i.selected ? 'checked' : ''} ${!i.valid ? 'disabled' : ''}>${image(i.image, '', i.name)}<div class="grow"><h3>${e(i.name)}</h3><p class="muted">${e(i.unit)}${!i.valid ? ' · 库存不足或已下架' : ''}</p>${fulfillmentBadge(i)}<div class="row spread" style="margin-top:9px">${amount(i.price_cents)}<div class="stepper"><button data-action="cart-minus" data-id="${i.id}" aria-label="减少${e(i.name)}">−</button><output>${i.quantity}</output><button data-action="cart-plus" data-id="${i.id}" aria-label="增加${e(i.name)}" ${i.quantity >= i.available ? 'disabled' : ''}>+</button></div></div><button class="cart-remove" data-action="cart-remove" data-id="${i.id}">移除</button></div></article>`).join('')}</div><section class="card bill"><h3>这一单，刚刚好</h3><div class="bill-line"><span>已选好物</span><b>${valid.reduce((n, i) => n + i.quantity, 0)} 件</b></div><div class="bill-line"><span>商品合计</span><b>¥${money(S.cart.subtotal_cents)}</b></div><div class="bill-line"><span>优惠券 / 配送费</span><span>结算时确认</span></div><div class="bill-total"><b>商品金额</b>${amount(S.cart.subtotal_cents)}</div>${button('去结算 ' + icon('arrow'), 'checkout', 'primary', !valid.length ? 'disabled' : '')}<p class="footnote">未付款订单保留15分钟<br>实验室不会产生真实扣款</p></section></div>`;
}
async function checkoutView() {
    if (!S.checkout?.length)
        return `${head('确认订单')}${empty('还没有选择商品', '先把想买的东西加入购物车。', '<a class="button primary" href="#/cart">回购物车</a>')}`;
    const [addresses, coupons] = await Promise.all([api('/addresses'), api('/coupons')]);
    if (!S.addressId && addresses.length)
        S.addressId = addresses[0].id;
    const data = { store_id: 1, items: S.checkout, method: S.method, address_id: S.method === 'delivery' ? S.addressId : null, coupon_id: S.couponId };
    try {
        S.quote = await api('/quotes', 'POST', data);
        S.quoteError = '';
    }
    catch (error) {
        S.quote = null;
        S.quoteError = error.message;
    }
    S.viewData = { addresses, coupons };
    S.checkoutKey = uniqueKey('checkout');
    const lines = S.quote?.items || S.checkout.map(i => { const p = S.products.find(p => p.id === i.sku_id); return { ...p, sku_id: i.sku_id, quantity: i.quantity, name: p?.name || '商品', price_cents: p?.price_cents || 0, image: p?.image || 'daily' }; });
    const q = S.quote;
    return `${head('确认订单', '最后确认一下，新鲜马上出发。')}<div class="checkout-layout"><div class="stack"><section class="card"><h3 style="margin-bottom:18px">怎么把新鲜带回家</h3>${deliveryTerms()}<div class="method-switch"><button data-action="method" data-method="pickup" class="${S.method === 'pickup' ? 'selected' : ''}">${icon('store')} 到店自提<small>不收配送费 · 凭核销码取货</small></button><button data-action="method" data-method="delivery" class="${S.method === 'delivery' ? 'selected' : ''}">${icon('truck')} 门店配送<small>${S.store.local_preview ? '园区边界待确认' : S.store.radius_km + 'km 演练范围'} · 满${money(S.store.minimum_cents)}起送</small></button></div>${S.method === 'pickup' ? `<div class="address-card"><b>${icon('pin')} ${e(S.store.name)}</b><p>${S.store.local_preview ? e(S.store.address) : '示例门店地址（虚构）'}，下单后等待店员完成打包。</p></div>` : `<div class="field"><label for="checkout-address">收货地址</label><select id="checkout-address" data-change="address-select"><option value="">请选择收货地址</option>${addresses.map(a => `<option value="${a.id}" ${S.addressId === a.id ? 'selected' : ''}>${e(a.name)} · ${e(a.address)}</option>`).join('')}</select></div>${button('管理 / 新增地址', 'address-new', 'outline sm')}<p class="footnote" style="margin-top:10px">配送范围由服务端根据地址坐标计算，不能由客户端伪造。</p>`}</section><section class="card"><h3>选好的商品</h3>${lines.map(i => `<div class="order-line">${image(i.image, '', i.name)}<div class="grow"><h3>${e(i.name)}</h3><p>${e(i.unit)} · ×${i.quantity}</p>${fulfillmentBadge(i)}</div>${amount(i.price_cents * i.quantity)}</div>`).join('')}</section></div><section class="card bill"><h3>订单明细</h3><div class="field"><label for="coupon-select">选择优惠券（每单限1张，不叠加）</label><select id="coupon-select" data-change="coupon-select"><option value="">不使用优惠券</option>${coupons.filter(c => c.state === 'available' && !c.expired).map(c => `<option value="${c.id}" ${S.couponId === c.id ? 'selected' : ''}>${e(c.title)}</option>`).join('')}</select></div>${S.quoteError ? `<div class="alert error" role="alert">${e(S.quoteError)}</div>` : ''}<div class="bill-line"><span>商品金额</span><b>${q ? '¥' + money(q.subtotal_cents) : '—'}</b></div><div class="bill-line"><span>优惠券抵扣</span><b class="orange">${q ? '- ¥' + money(q.discount_cents) : '—'}</b></div>${q ? shippingBreakdown(q.shipping_detail, S.method) : ''}<div class="bill-line"><span>配送费合计</span><b>${q ? '¥' + money(q.shipping_cents) : '—'}</b></div><div class="bill-total"><b>应付合计</b>${q ? amount(q.total_cents) : '—'}</div>${button('提交订单', 'place-order', 'primary', !q ? 'disabled' : '')}<p class="footnote">服务端实时报价 · 有效期2分钟<br>提交后再模拟付款，不会真实扣款</p></section></div>`;
}
const statusPill = o => `<span class="pill ${['pending_payment', 'refund_pending'].includes(o.state) ? 'amber' : ['cancelled', 'refunded'].includes(o.state) ? 'red' : ''}">${e(states[o.state] || o.state)}</span>`;
function orderCard(o) { return `<section class="card order-card"><div class="order-card-head"><div><b>${o.method === 'pickup' ? '到店自提' : '门店配送'}</b> <span class="order-id">${e(o.number)}</span></div>${statusPill(o)}</div><a href="#/order?id=${e(o.id)}"><div class="order-thumbs">${o.items.slice(0, 5).map(i => image(i.image, '', i.name)).join('')}<span class="muted">共${o.items.reduce((n, i) => n + i.quantity, 0)}件</span></div><p class="muted" style="font-size:11px">${o.items.map(i => e(i.name)).join('、')} · ${timeLabel(o.created)}</p></a><div class="order-card-foot"><div><small class="muted">${o.paid_cents ? '实付' : '应付'} </small>${amount(o.total_cents)}${o.refunded_cents ? `<small class="orange"> 已退 ¥${money(o.refunded_cents)}</small>` : ''}</div><a class="button ${o.state === 'pending_payment' && isCustomer() ? 'buy' : 'secondary'} sm" href="#/order?id=${e(o.id)}">${o.state === 'pending_payment' && isCustomer() ? '去付款' : isCustomer() ? '查看订单' : '处理订单'} ${icon('arrow')}</a></div></section>`; }
async function ordersView(q) {
    const orders = await api('/orders');
    S.viewData = orders;
    const filter = q.get('status') || 'all';
    const filtered = orders.filter(o => filter === 'all' || filter === o.state || (filter === 'after_sale' && o.refunds.length));
    const tabs = isCustomer() ? [['all', '全部'], ['pending_payment', '待付款'], ['paid', '待接单'], ['delivering', '配送中'], ['completed', '已完成'], ['after_sale', '售后']] : [['all', '全部'], ['paid', '待接单'], ['picking', '拣货中'], ['ready', '待取货'], ['delivering', '配送中'], ['completed', '已完成'], ['after_sale', '退款售后']];
    return `${head(isCustomer() ? '我的订单' : '订单履约', isCustomer() ? '每一份新鲜，都有迹可循。' : '接单、拣货、打包与配送，同一本订单账。', button(icon('refresh') + '刷新', 'refresh', 'outline'))}<div class="chips">${tabs.map(([v, l]) => `<a class="chip ${filter === v ? 'active' : ''}" href="#/orders?status=${v}">${l}${v === 'all' ? ' · ' + orders.length : ''}</a>`).join('')}</div>${filtered.length ? filtered.map(orderCard).join('') : empty('这里还没有订单', isCustomer() ? '喜欢的好物，下次不再错过。' : '切换到顾客身份下一单，或者在实验室创建演练订单。', isCustomer() ? '<a class="button primary" href="#/home">去逛超市</a>' : button('以顾客身份下一单', 'shop', 'primary'))}`;
}
async function orderView(q) {
    const o = await api('/orders/' + q.get('id'));
    S.viewData = o;
    const subtitle = { pending_payment: '商品已预留，请在15分钟内完成模拟付款。', paid: '门店正在确认订单，你的新鲜正在准备中。', picking: '店员正在逐件拣选商品，请稍等片刻。', ready: o.method === 'pickup' ? '已打包完成，请向店员出示下方核销码。' : '已打包完成，等待配送员取货。', delivering: '模拟骑手已取货，新鲜正在路上。', completed: '感谢这一份信任，愿你今天吃得开心。', cancelled: '订单已关闭，未付款库存已释放。', refund_pending: '退款任务处理中，金额到账后会更新状态。', refunded: '模拟款项已退回，不会产生真实资金变化。' }[o.state];
    let actions = '';
    if (isCustomer()) {
        if (S.store.local_preview && ['paid','picking','ready','delivering'].includes(o.state))
            actions = button(o.state === 'delivering' ? '取消订单（扣2元配送费）' : '取消并退款', 'cancel-order', 'outline', `data-id="${o.id}"`);
        if (o.state === 'pending_payment')
            actions = button('模拟微信付款', 'pay', 'buy', `data-id="${o.id}"`) + button('取消订单', 'cancel-order', 'outline', `data-id="${o.id}"`);
        if (o.state === 'completed' && !o.refunds.some(r => ['requested', 'pending', 'failed'].includes(r.state)))
            actions = button('申请售后', 'aftersale', 'outline', `data-id="${o.id}"`);
    }
    else {
        if (o.state === 'paid')
            actions = button('接单并开始拣货', 'accept', 'primary', `data-id="${o.id}"`);
        if (o.state === 'picking')
            actions = button('全部拣齐', 'pick-all', 'secondary', `data-id="${o.id}"`) + button('完成打包', 'ready', 'primary', `data-id="${o.id}"`);
        if (o.state === 'ready' && o.method === 'pickup')
            actions = button('输入核销码取货', 'pickup', 'primary', `data-id="${o.id}"`);
        if (o.state === 'ready' && o.method === 'delivery' && !o.delivery)
            actions = button('呼叫模拟骑手', 'dispatch', 'primary', `data-id="${o.id}"`);
        if (isManager() && ['paid', 'picking', 'ready'].includes(o.state))
            actions += button('取消并退款', 'cancel-order', 'danger', `data-id="${o.id}"`);
    }
    const track = o.delivery ? ['created', 'accepted', 'picked_up', 'delivered'].indexOf(o.delivery.state) : -1;
    return `<a href="#/orders" class="breadcrumb">${icon('back')}返回订单列表</a><section class="order-status-hero"><div class="status-icon">${icon(o.state === 'completed' ? 'check' : o.state === 'delivering' ? 'truck' : 'bag')}</div><div class="grow"><h2>${e(states[o.state])}</h2><p>${subtitle}</p></div>${button(icon('refresh'), 'refresh', 'outline sm', 'aria-label="刷新订单"')}</section><div class="checkout-layout"><div class="stack"><section class="card"><div class="row spread"><h3>${o.method === 'pickup' ? '到店自提' : '门店配送'}</h3><span class="order-id">${e(o.number)}</span></div>${o.method === 'delivery' ? `<div class="address-card"><b>${e(o.address.name)}　${e(phoneEncryption(o.address.mobile || ''))}</b><p>${e(o.address.address)}</p></div>` : ''}${o.method === 'pickup' && isCustomer() && ['ready', 'completed'].includes(o.state) ? `<div class="address-card"><small class="muted">自提核销码 · 请向店员出示</small><div class="pickup-code">${o.pickup_code}</div><small class="muted">${o.state === 'completed' ? '该订单已核销' : '门店核验后，订单才会完成'}</small></div>` : ''}${o.items.map(l => `<div class="order-line">${image(l.image, '', l.name)}<div class="grow"><h3>${e(l.name)}</h3><p>${e(l.unit)} · ×${l.quantity}${l.shortage_qty ? ' · 缺货' + l.shortage_qty + '件' : ''}${!isCustomer() ? ' · 已拣' + l.picked_qty + '件' : ''}</p>${!isCustomer() && o.state === 'picking' ? `<div class="row wrap" style="margin-top:8px">${button('已拣齐', 'pick-line', 'secondary sm', `data-line="${l.id}" ${l.picked_qty + l.shortage_qty >= l.quantity ? 'disabled' : ''}`)}${button('缺1件退款', 'shortage', 'danger sm', `data-line="${l.id}" ${l.picked_qty + l.shortage_qty >= l.quantity ? 'disabled' : ''}`)}</div>` : ''}</div><div>${amount(l.net_cents)}${l.discount_cents ? `<p class="muted">已减 ¥${money(l.discount_cents)}</p>` : ''}</div></div>`).join('')}${shippingBreakdown(o.shipping_detail, o.method)}<div class="bill-line"><span>配送费合计</span><b>¥${money(o.shipping_cents)}</b></div><div class="bill-total"><b>应付合计</b>${amount(o.total_cents)}</div>${o.refunded_cents ? `<div class="bill-line"><span>已退款</span><b class="orange">¥${money(o.refunded_cents)}</b></div>` : ''}${actions ? `<div class="order-actions row wrap" style="margin-top:23px">${actions}</div>` : ''}</section>${o.delivery ? `<section class="card"><h3>${icon('truck')} 配送进度</h3><p class="subtitle">${e(o.delivery.courier)} · 模拟配送服务</p><div class="delivery-track">${['已呼叫', '已接单', '已取货', '已送达'].map((v, n) => `<div class="track-step ${n <= track ? 'done' : ''}">${icon(n === 3 ? 'check' : 'truck')}${v}</div>`).join('')}</div>${!isCustomer() && isManager() && track >= 0 && track < 3 ? button('推进模拟骑手：' + ['接单', '取货', '送达'][track], 'advance-delivery', 'secondary', `data-id="${o.delivery.id}" data-state="${['accepted', 'picked_up', 'delivered'][track]}"`) : ''}<p class="footnote">由模拟骑手事件驱动，不是实时 GPS 地图。</p></section>` : ''}${o.refunds.length ? `<section class="card"><h3>退款与售后</h3>${o.refunds.map(r => `<div class="job"><div class="row spread"><b>¥${money(r.amount_cents)}</b><span class="pill ${r.state === 'failed' ? 'red' : ''}">${e({ requested: '等待店长审核', pending: '退款处理中', failed: '退款失败 · 可重试', succeeded: '模拟退款到账', rejected: '申请未通过' }[r.state])}</span></div><small>${e(r.reason)}</small>${r.state === 'requested' && isManager() ? `<div class="row" style="margin-top:10px">${button('同意退款', 'approve-refund', 'primary sm', `data-id="${r.id}"`)}${button('拒绝申请', 'reject-refund', 'outline sm', `data-id="${r.id}"`)}</div>` : ''}</div>`).join('')}</section>` : ''}</div><section class="card"><h3>这一单的每一步</h3><p class="footnote">来自数据库的真实状态记录</p><div class="timeline">${o.timeline.map(t => `<div class="timeline-item">${e(events[t.action] || t.action)}<small>${timeLabel(t.created)}</small></div>`).join('')}</div><div class="footnote">订单编号 ${e(o.number)}<br>支付与退款仅在本地模拟账本中流转。</div></section></div>`;
}
async function dashboard() {
    const d = await api('/admin/dashboard');
    S.viewData = d;
    const list = [['累计订单', d.order_count, 'file', '本地数据库订单数'], ['模拟净收款', '¥' + money(d.net_cents), 'wallet', '付款减已完成退款'], ['待接单', d.waiting, 'clock', '已付款，等待门店确认'], ['低库存商品', d.low_stock, 'bag', '可售库存低于10份']];
    const chart = [['待接单', 'paid'], ['拣货中', 'picking'], ['待取货', 'ready'], ['已完成', 'completed']];
    const max = Math.max(1, ...chart.map(([l, k]) => d.states[k]));
    const actions = [['orders', 'file', '订单管理', '接单 · 拣货 · 售后'], ['inventory', 'box', '商品库存', '价格 · 入库 · 盘点'], ['marketing', 'ticket', '会员营销', '发券 · 分类 · 会员'], ['settings', 'store', '门店设置', '范围 · 营业 · 运费'], ['receipts', 'print', '打印记录', '小票 · 失败重试'], ['lab', 'code', '联调实验室', '故障注入 · 数据对账']];
    return `${head('门店经营，一目了然。', `${e(S.store.name)} · 欢迎回来，${e(S.user.name)}。`, button(icon('refresh') + '刷新数据', 'refresh', 'outline'), 'STORE / OPERATIONS')}` +
        `<div class="stats-grid">${list.map(([l, v, i, n]) => `<section class="stat-card">${icon(i)}<p>${l}</p><b>${v}</b><small>${n}</small></section>`).join('')}</div><div class="dashboard-grid"><section class="card"><div class="row spread"><h3>门店工作台</h3><span class="pill">${S.store.open ? '营业中' : '已打烊'}</span></div><p class="subtitle">让好物及时送到，让每一笔账都清楚。</p><div class="actions-grid">${actions.filter(a => isManager() || a[0] === 'orders').map(([p, i, l, n]) => `<button class="quick-action" data-action="quick" data-page="${p}">${icon(i)}${l}<small>${n}</small></button>`).join('')}</div></section><section class="card"><h3>订单状态分布</h3><p class="subtitle">待接单、拣货、待取货与已完成订单，不含取消和退款。</p><div class="bar-chart">${chart.map(([l, k]) => `<div class="bar-column">${d.states[k]}<i style="height:${Math.max(2, Math.round(d.states[k] / max * 120))}px"></i></div>`).join('')}</div><div class="bar-labels">${chart.map(([l]) => `<span>${l}</span>`).join('')}</div></section><section class="card"><div class="row spread"><h3>最近业务动态</h3><span class="muted">实时审计</span></div>${d.recent.length ? d.recent.slice(0, 7).map(a => `<div class="activity-row"><div class="circle">${icon('check')}</div><div class="grow"><b>${e(events[a.action] || a.action)}</b><small>${e(a.entity)}</small></div><small>${timeLabel(a.created)}</small></div>`).join('') : '<p class="subtitle" style="padding:25px 0">下一笔订单，就从现在开始。</p>'}</section><section class="card"><div class="eyebrow">LABORATORY / LIVE DATA</div><h3>把复杂留给系统，<br>把新鲜留给顾客。</h3><p class="subtitle" style="line-height:2;margin:14px 0 22px">每笔订单都经过服务端核价，<br>每次库存变动都有流水，<br>每次支付回调都验证签名。</p>${button('进入顾客端下一单 ' + icon('arrow'), 'shop', 'secondary')}<p class="footnote" style="margin-top:18px">此处展示的是本地演练数据，不代表真实门店经营业绩。</p></section></div>`;
}
async function inventory(q) {
    const keyword = q.get('q') || '';
    const products = S.products.filter(p => !keyword || p.name.includes(keyword) || p.barcode === keyword);
    S.viewData = products;
    return `${head('商品与库存', '商品售价、可售库存和库存流水，统一管理。', button(icon('plus') + '新增商品', 'product-new', 'primary'), 'STORE / INVENTORY')}<div class="toolbar">${searchForm(keyword, 'inventory')}${button('库存流水', 'stock-ledger', 'outline')}${S.store.local_preview ? button('导入核对', 'import-review', 'outline') : ''}</div><div class="table-wrap"><table><thead><tr><th>商品 / 规格</th><th>售价</th><th>账面库存</th><th>预占</th><th>可售</th><th>状态</th><th>操作</th></tr></thead><tbody>${products.map(p => `<tr data-sku="${p.id}"><td>${image(p.image, '', p.name)}<b>${e(p.name)}</b><div class="footnote">${e(p.unit)} · ${e(p.barcode)}</div>${fulfillmentBadge(p)}<div class="footnote">配送重量：${p.weight_g == null ? '未确认' : p.weight_g + '克 / ' + e(p.unit)}</div></td><td>¥${money(p.price_cents)}</td><td>${p.on_hand}</td><td>${p.reserved}</td><td class="${p.available < 10 ? 'stock-low' : ''}">${p.available}</td><td><span class="pill ${p.active ? '' : 'red'}">${p.active ? '上架中' : '已下架'}</span></td><td><div class="inventory-actions">${button('库存', 'stock-edit', 'secondary sm', `data-id="${p.id}"`)}${button('改价', 'price-edit', 'outline sm', `data-id="${p.id}"`)}${button('配送资料', 'fulfillment-edit', 'outline sm', `data-id="${p.id}"`)}${button(p.active ? '下架' : '上架', 'toggle-product', 'outline sm', `data-id="${p.id}"`)}</div></td></tr>`).join('')}</tbody></table></div><div class="alert">库存含义：账面数量 − 未付款订单预占 = 可售数量。线下销售通过模拟 POS 事件入账；不能直接覆盖库存数。</div>`;
}
async function settings() {
    // A separate form avoids silently confirming provisional merchant terms.
    const ruleAction = S.store.delivery_rules ? button('配送时间与超重规则', 'delivery-rules-edit', 'outline') : '';
    return `${head('门店设置', '每个规则都由服务端执行，客户端只负责展示。', ruleAction, 'STORE / SETTINGS')}<div class="checkout-layout"><section class="card"><form data-form="settings"><div class="field"><label>营业状态</label><select name="open"><option value="1" ${S.store.open ? 'selected' : ''}>营业中</option><option value="0" ${!S.store.open ? 'selected' : ''}>已打烊</option></select></div><div class="field-row"><div class="field"><label>配送范围（km）</label><input name="radius" type="number" min="0.1" step="0.1" max="50" value="${S.store.radius_km}" required></div><div class="field"><label>起送金额（元）</label><input name="minimum" inputmode="decimal" value="${money(S.store.minimum_cents)}" required></div></div><div class="field-row"><div class="field"><label>基础配送费（元）</label><input name="delivery" inputmode="decimal" value="${money(S.store.delivery_cents)}" required></div><div class="field"><label>免基础配送费门槛（元）</label><input name="free" inputmode="decimal" value="${money(S.store.free_shipping_cents)}" required></div></div><button class="button primary">保存门店设置</button></form></section><section class="card"><h3>本店履约规则</h3>${deliveryTerms()}<p class="subtitle" style="line-height:2.1">免基础配送费按优惠后的商品金额计算，超重费另计。<br>配送距离按门店与地址坐标计算。<br>已关闭的门店不再接受新订单。<br>已有已付款订单仍可继续履约。</p><div class="alert">此版本使用示例坐标与直线距离进行范围演练，不代表道路里程，也未连接地图厂商。</div></section></div>`;
}
async function lab() {
    const [r, lab] = await Promise.all([api('/admin/reconciliation'), api('/lab/state')]);
    S.viewData = { r, lab };
    const faults = [['printer_offline', '让打印机离线', '支付不受影响，小票进入可重试队列。'], ['refund_failure', '让退款网关超时', '保留退款申请，不把失败误报为到账。'], ['delivery_unavailable', '让配送平台不可用', '订单保留在待取货状态，恢复后再派单。']];
    return `${head('联调实验室', '故障可以模拟，账本不能含糊。', button(icon('refresh') + '重新检查', 'refresh', 'outline'), 'LAB / ACCEPTANCE')}<section class="lab-banner"><div class="row spread"><div><div class="eyebrow" style="color:#98bb83">SAFE BY DESIGN / LOCAL ONLY</div><h2>在安全的环境里，把问题提前找出来。</h2><p>真实 SQL 事务、真实 HTTP 接口。只有支付、配送、打印和 POS 服务是模拟的。</p></div><span class="pill header-status">● 本地运行中</span></div></section><div class="lab-grid"><section class="card"><div class="row spread"><h3>交易与库存一致性</h3><span class="pill">刚刚检查</span></div><div class="reconcile-hero"><div class="reconcile-circle">${icon(r.ok ? 'shield' : 'clock')}</div><h3>${r.ok ? '所有账本一致' : '存在待确认或异常记录'}</h3><p>${r.ok ? '库存流水、订单金额与模拟网关账单相互吻合。' : '请检查付款回调与下方任务队列。'}</p></div><div class="check-grid"><div><small>已检查商品</small><b>${r.checked_skus} 个</b></div><div><small>已检查订单</small><b>${r.checked_orders} 笔</b></div><div><small>模拟收款</small><b>¥${money(r.paid_cents)}</b></div><div><small>已完成模拟退款</small><b>¥${money(r.refunded_cents)}</b></div></div><div class="row wrap">${button('运行一致性检查', 'refresh', 'primary')}${button('导出对账数据', 'export', 'outline')}</div>${r.issues.length ? `<div class="alert error">${e(JSON.stringify(r.issues))}</div>` : ''}<p class="footnote" style="margin-top:12px">一致性检查不等于完整安全审计。自动化验收记录随源码包附带。</p></section><section class="card"><h3>故障注入</h3><p class="subtitle">打开开关后，实际调用对应业务来验证失败路径。</p>${faults.map(([k, l, d]) => `<div class="fault-row"><div><b>${l}</b><p>${d}</p></div><button class="toggle ${lab.switches[k] ? 'on' : ''}" role="switch" aria-checked="${lab.switches[k]}" aria-label="${l}" data-action="fault" data-key="${k}"></button></div>`).join('')}<div class="row wrap" style="margin-top:21px">${button(icon('refresh') + '重试待处理任务', 'worker', 'secondary')}${button('创建一笔演练订单', 'sample-order', 'outline')}</div></section><section class="card"><div class="row spread"><h3>可靠任务队列</h3><small class="muted">${lab.outbox.filter(j => j.state !== 'done').length} 条待处理</small></div>${lab.outbox.length ? lab.outbox.slice(0, 10).map(j => `<div class="job"><div class="row spread"><b>${{ print: '订单小票', notify: '顾客通知', refund: '原路退款' }[j.kind] || e(j.kind)}</b><span class="pill ${j.state === 'failed' ? 'red' : ''}">${{ pending: '待处理', failed: '失败，可重试', done: '已完成' }[j.state]}</span></div><small>${e(j.reference)} · 尝试 ${j.attempts} 次${j.error ? ' · ' + e(j.error) : ''}</small></div>`).join('') : '<p class="subtitle" style="margin:24px 0">支付后产生通知和小票任务。</p>'}</section><section class="card"><div class="row spread"><h3>模拟支付网关账本</h3><span class="pill amber">非真实资金</span></div>${lab.gateway_ledger.length ? lab.gateway_ledger.slice(0, 10).map(g => `<div class="job"><div class="row spread"><span>${g.kind === 'charge' ? '模拟收款' : '模拟退款'}</span><b class="${g.kind === 'refund' ? 'orange' : 'green'}">${g.kind === 'refund' ? '−' : '＋'} ¥${money(g.amount_cents)}</b></div><small>${e(g.order_id)} · ${timeLabel(g.created)}</small></div>`).join('') : '<p class="subtitle" style="margin:24px 0">目前还没有模拟资金流水。</p>'}</section></div>`;
}
async function profile() {
    const [orders, coupons, notifications] = await Promise.all([api('/orders'), api('/coupons'), api('/notifications')]);
    S.viewData = { orders, coupons, notifications };
    const links = [['addresses', 'pin', '我的地址', '管理收货地址'], ['coupons', 'ticket', '优惠券', coupons.filter(c => c.state === 'available' && !c.expired).length + '张可用'], ['favorites', 'heart', '收藏好物', '喜欢的，下次再来'], ['notifications', 'bell', '消息通知', notifications.length + '条动态'], ['support', 'headset', '联系客服', '演练服务说明'], ['about', 'file', '关于我们', '新鲜好物 · 健康每一天']];
    return `<section class="profile-hero"><div class="eyebrow" style="color:#d5e7c7">A LITTLE FRESHNESS, EVERY DAY</div><div class="row" style="margin-top:18px">${image('avatar', '', S.user.name)}<div><div class="row wrap"><h1>${e(S.user.name)}</h1><span class="pill amber">社区会员 · 演练</span></div><p>陪你发现，更好的日常。</p></div></div></section><section class="card" style="margin-bottom:19px"><div class="row spread"><h3>我的订单</h3><a class="muted" href="#/orders">全部订单 ${icon('arrow')}</a></div><div class="actions-grid" style="grid-template-columns:repeat(4,1fr)">${[['pending_payment', 'wallet', '待付款'], ['paid', 'clock', '待接单'], ['delivering', 'truck', '配送中'], ['completed', 'box', '已完成']].map(([s, i, l]) => `<a class="quick-action" href="#/orders?status=${s}">${icon(i)}${l}<small>${orders.filter(o => o.state === s).length} 笔</small></a>`).join('')}</div></section><div class="profile-menu">${links.map(([p, i, l, n]) => `<button class="menu-row" data-action="profile-link" data-page="${p}">${icon(i)}<div class="grow" style="text-align:left"><b>${l}</b><p class="footnote">${n}</p></div>${icon('arrow')}</button>`).join('')}</div><button class="menu-row" style="margin-top:20px;width:100%" data-action="work">${icon('store')}<div class="grow" style="text-align:left"><b>切换门店演练身份</b><p class="footnote">实验室入口 · 正式系统不开放此切换能力</p></div>${icon('arrow')}</button>`;
}
async function addressesView() {
    const addresses = await api('/addresses');
    S.viewData = addresses;
    return `${head('收货地址', '所有预置地址都是演练资料。', button(icon('plus') + '新增地址', 'address-new', 'primary'))}<div class="stack">${addresses.map(a => `<section class="card"><div class="row spread"><b>${e(a.name)}　${e(phoneEncryption(a.mobile))}</b><div class="row">${button('编辑', 'address-edit', 'outline sm', `data-id="${a.id}"`)}${button('删除', 'address-delete', 'outline sm', `data-id="${a.id}"`)}</div></div><p class="subtitle">${e(a.address)}</p><p class="footnote" style="margin-top:8px">演练坐标 ${a.latitude}, ${a.longitude}</p></section>`).join('') || empty('还没有收货地址', '可以手动填写，不需要强制定位授权。')}</div>`;
}
async function couponsView() {
    const coupons = await api('/coupons');
    return `${head('我的优惠券', '把实惠留给日常，把好物带回家。')}<div class="coupon-grid">${coupons.map(c => `<section class="coupon" style="opacity:${c.state === 'available' && !c.expired ? 1 : .55}"><div class="coupon-value"><b>¥${money(c.discount_cents).replace('.00', '')}</b><small>满${money(c.minimum_cents)}可用</small></div><div class="coupon-info"><h3>${e(c.title)}</h3><small>${c.expired ? '已过期' : { available: '待使用', reserved: '订单已预占', used: '已使用' }[c.state]} · ${timeLabel(c.expires)} 到期</small><a class="text-button" href="#/home">去逛好物 ${icon('arrow')}</a></div></section>`).join('')}</div>`;
}
async function marketing() {
    const members = await api('/admin/members');
    return `${head('会员与营销', '简单实用的门店工具，不必把日常经营变复杂。', '', 'STORE / MEMBERS')}<div class="row wrap" style="margin-bottom:22px">${isOperator() ? button(icon('ticket') + '发放优惠券', 'coupon-new', 'primary') + button(icon('grid') + '新增商品分类', 'category-new', 'outline') : ''}</div><section class="card" style="margin-bottom:20px"><h3>商品分类</h3><div class="row wrap" style="margin-top:15px">${S.categories.map(c => `<span class="pill">${e(c.name)}</span>`).join('')}</div></section><section class="card"><h3>有成交记录的会员</h3><p class="subtitle" style="margin-bottom:20px">按当前门店订单统计，不泄露其他门店顾客资料。</p><div class="table-wrap"><table><thead><tr><th>会员</th><th>订单数</th><th>模拟净消费</th></tr></thead><tbody>${members.map(m => `<tr><td>${e(m.name)}</td><td>${m.orders}</td><td>¥${money(m.net_cents)}</td></tr>`).join('') || '<tr><td colspan="3">暂无成交会员</td></tr>'}</tbody></table></div></section>`;
}
async function rider() {
    const tasks = await api('/rider/tasks');
    S.viewData = tasks;
    return `${head('配送任务', '每一步配送都有记录，电话按权限脱敏。', button(icon('refresh') + '刷新', 'refresh', 'outline'), 'STORE / DELIVERY')}<div class="stack">${tasks.map(t => { const idx = ['created', 'accepted', 'picked_up', 'delivered'].indexOf(t.state); return `<section class="card"><div class="row spread"><h3>${e(t.number)}</h3><span class="pill">${{ created: '等待接单', accepted: '等待取货', picked_up: '配送中', delivered: '已送达', cancelled: '已取消' }[t.state]}</span></div><div class="address-card"><b>${e(t.contact)}　${e(t.mobile_masked)}</b><p>${e(t.address)}</p></div><p class="footnote">${e(t.courier)} · 模拟任务</p>${idx >= 0 && idx < 3 ? button(['接受配送单', '确认已取货', '确认已送达'][idx], 'advance-delivery', 'primary', `data-id="${t.id}" data-state="${['accepted', 'picked_up', 'delivered'][idx]}" style="margin-top:15px"`) : ''}</section>`; }).join('') || empty('还没有配送任务', '先在店员端完成打包并呼叫模拟骑手。')}</div>`;
}
async function render() {
    const seq = ++S.sequence;
    if (!S.token || !S.user) {
        renderLogin();
        return;
    }
    const { page, query } = route();
    S.rendering = true;
    root.setAttribute('aria-busy', 'true');
    try {
        await globals();
        let content;
        const customerPages = ['home', 'categories', 'product', 'cart', 'checkout', 'profile', 'addresses', 'coupons', 'favorites'];
        if (!isCustomer() && customerPages.includes(page)) {
            go(S.user.role === 'rider' ? 'rider' : 'dashboard');
            return;
        }
        switch (page) {
            case 'home':
                content = home();
                break;
            case 'categories':
                content = categories(query);
                break;
            case 'product':
                content = await detail(query);
                break;
            case 'cart':
                content = cartView();
                break;
            case 'checkout':
                content = await checkoutView();
                break;
            case 'orders':
                content = await ordersView(query);
                break;
            case 'order':
                content = await orderView(query);
                break;
            case 'dashboard':
                content = await dashboard();
                break;
            case 'inventory':
                content = await inventory(query);
                break;
            case 'settings':
                content = await settings();
                break;
            case 'lab':
                content = await lab();
                break;
            case 'profile':
                content = await profile();
                break;
            case 'addresses':
                content = await addressesView();
                break;
            case 'coupons':
                content = await couponsView();
                break;
            case 'marketing':
                content = await marketing();
                break;
            case 'rider':
                content = await rider();
                break;
            case 'favorites': {
                const ids = await api('/favorites');
                content = head('收藏好物', '喜欢的东西，留给下次相遇。') + `<div class="product-grid">${S.products.filter(p => ids.includes(p.id)).map(p => productCard(p)).join('')}</div>`;
                if (!ids.length)
                    content += empty('还没有收藏好物', '到商品详情页点一下收藏就好。');
                break;
            }
            default:
                go(isCustomer() ? 'home' : 'dashboard');
                return;
        }
        if (seq === S.sequence) {
            root.innerHTML = shell(content, page);
            document.title = (isCustomer() ? '京漫便民 · 新鲜就在身边' : '京漫便民 · 门店工作台');
        }
    }
    catch (error) {
        if (error.status === 401) {
            S.token = '';
            renderLogin();
            toast('登录已过期，请重新进入');
            return;
        }
        if (seq === S.sequence)
            root.innerHTML = S.store ? shell(head('暂时没有打开') + `<div class="alert error">${e(error.message)}</div>` + button('重试', 'refresh', 'primary'), page) : `<div class="boot">${e(error.message)}<button data-action="refresh">重试</button></div>`;
        console.error('view', error.message);
    }
    finally {
        if (seq === S.sequence) {
            S.rendering = false;
            root.setAttribute('aria-busy', 'false');
        }
    }
}
function renderLogin() { root.innerHTML = `<main class="login-wrap"><section class="login-card">${brand()}<div class="eyebrow">LOCAL INTEGRATION LAB / V0.2</div><h1>让这家超市，真正运转起来。</h1><p class="subtitle">订单、库存与账本会真实保存。<br>支付、配送与打印在安全的本地环境中模拟。</p><form data-form="login"><div class="field"><label for="access-key">实验室访问口令</label><input id="access-key" type="password" name="key" autocomplete="off" placeholder="粘贴启动终端显示的口令" required minlength="12" value="${e(S.key)}"></div><button class="button primary">进入京漫便民 ${icon('arrow')}</button></form><p class="footnote" style="margin-top:20px">运行 ./run.sh 后，使用终端给出的地址进入。<br>此程序只用于本地验收，不连接真实微信钱包。</p></section></main>`; }
let lastFocus = null;
function modal(title, body) { lastFocus = document.activeElement; overlay.innerHTML = `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="${e(title)}"><div class="modal-head"><h2>${title}</h2><button class="icon-button" data-action="close" aria-label="关闭弹窗">${icon('close')}</button></div>${body}</section></div>`; overlay.querySelector('input,select,textarea,button')?.focus(); }
function closeModal() { overlay.innerHTML = ''; lastFocus?.focus?.(); }
function addressModal(a = {}) { modal(a.id ? '编辑收货地址' : '新增收货地址', `<form data-form="address" data-id="${a.id || ''}"><div class="field-row"><div class="field"><label>收件人</label><input name="name" value="${e(a.name || '体验用户')}" required maxlength="30"></div><div class="field"><label>手机号（演练）</label><input name="mobile" value="${e(a.mobile || '18800000001')}" required pattern="1[0-9]{10}" inputmode="tel"></div></div><div class="field"><label>详细地址</label><input name="address" value="${e(a.address || '示例小区 2号楼201（虚构地址）')}" minlength="4" maxlength="160" required></div><div class="field-row"><div class="field"><label>地址纬度</label><input name="latitude" type="number" step="any" min="-90" max="90" value="${a.latitude ?? 31.234}" required></div><div class="field"><label>地址经度</label><input name="longitude" type="number" step="any" min="-180" max="180" value="${a.longitude ?? 121.48}" required></div></div><p class="footnote">预填地址是演练样例。改为32.23纬度可测试超配送范围；未授权定位也能手动填写。</p><div class="row wrap" style="margin-top:18px"><button class="button primary">保存地址</button><button class="button outline" type="button" data-action="locate">尝试定位</button></div></form>`); }
async function safe(action, buttonElement) {
    if (buttonElement?.disabled)
        return;
    if (buttonElement)
        buttonElement.disabled = true;
    S.pending++;
    try {
        await action();
    }
    catch (error) {
        toast(error.message || '操作未完成，请重试');
    }
    finally {
        S.pending--;
        if (buttonElement?.isConnected)
            buttonElement.disabled = false;
    }
}
async function persona(name, page) { if (!S.key) {
    renderLogin();
    return;
} await login(name); closeModal(); go(page || (name.startsWith('customer') ? 'home' : name === 'rider' ? 'rider' : 'dashboard')); }
async function perform(action, el) {
    const id = el?.dataset.id, oid = S.viewData?.id;
    switch (action) {
        case 'delivery-rules-edit': {
            const r = S.store.delivery_rules;
            modal('配送时间与超重规则', `<form data-form="delivery-rules" data-version="${S.store.version}"><div class="field-row"><div class="field"><label for="delivery-start">开始接配送单（北京时间）</label><input type="time" id="delivery-start" name="start" value="${e(r.start)}" required></div><div class="field"><label for="delivery-end">停止接配送单</label><input type="time" id="delivery-end" name="end" value="${e(r.end)}" required></div></div><div class="field"><label for="delivery-rounding">超过5千克的不足1千克部分</label><select name="rounding" id="delivery-rounding"><option value="ceil_kg" ${r.rounding === 'ceil_kg' ? 'selected' : ''}>按1千克计：5.2千克加1.50元</option><option value="proportional" ${r.rounding === 'proportional' ? 'selected' : ''}>按实际重量：5.2千克加0.30元</option></select></div><div class="field"><label class="confirmation"><input type="checkbox" name="hours_confirmed" ${!r.provisional_hours ? 'checked' : ''}> 商家已确认配送时段</label></div><div class="field"><label class="confirmation"><input type="checkbox" name="rounding_confirmed" ${!r.provisional_rounding ? 'checked' : ''}> 商家已确认超重取整口径</label></div><p class="footnote">前5千克不加超重费，之后每千克1.50元；每单限1张券。到结束时间起不再接配送单。保存不会开放园区配送边界，不会修改已有订单快照，也不会连接拉卡拉。</p><button class="button primary full">保存配送规则</button></form>`);
            return;
        }
        case 'fulfillment-edit': {
            const p = S.products.find(p => p.id === Number(id));
            modal('配送重量与自提 · ' + e(p.name), `<form data-form="fulfillment" data-id="${p.id}" data-version="${p.version}"><div class="field"><label>每销售单位的配送计费重量（克）</label><input name="weight" type="number" min="1" max="1000000" step="1" value="${p.weight_g ?? ''}" placeholder="留空表示未确认"/></div><p class="footnote">当前销售单位：${e(p.unit)}。请填写一${e(p.unit)}的实际配送重量；不要把毫升或商品名称中的净含量直接当成配送重量。缺少重量时仅可自提。</p><div class="field"><label>销售方式</label><select name="channel" ${p.fulfillment_note ? 'disabled' : ''}><option value="both" ${!p.pickup_only ? 'selected' : ''}>自提和配送</option><option value="pickup" ${p.pickup_only ? 'selected' : ''}>仅限自提</option></select></div>${p.fulfillment_note ? `<p>${e(p.fulfillment_note)}</p>` : ''}<button class="button primary full">保存</button></form>`);
            return;
        }
        case 'import-review': {
            const records = await api('/admin/import-review');
            const held = records.filter(r => JSON.parse(r.review_json).length);
            modal('商品导入核对', `<p>共${records.length}条来源记录，${held.length}条待核对。源库存保留原值，未覆盖收银系统。</p><div class="import-review-list">${held.map(r => `<div class="import-review-item"><b>${e(r.name)}</b><p>源行 ${r.source_row} · 原库存 ${e(r.source_stock)}</p><p>${e(JSON.parse(r.review_json).join('；'))}</p></div>`).join('')}</div>`);
            return;
        }
        case 'close':
            closeModal();
            return;
        case 'refresh':
            await render();
            return;
        case 'shop':
            await persona('customer', 'home');
            return;
        case 'work':
            await persona('manager', 'dashboard');
            return;
        case 'lab':
            await persona('manager', 'lab');
            return;
        case 'add': {
            const quantity = Number(el.dataset.quantity || 1), cart = await api('/cart');
            const old = cart.items.find(i => i.id === Number(id));
            await api('/cart', 'PUT', { sku_id: Number(id), quantity: (old?.quantity || 0) + quantity });
            await render();
            toast('已加入购物车');
            return;
        }
        case 'variant':
            S.quantity = 1;
            go('product', { id });
            return;
        case 'quantity-plus':
            S.quantity = Math.min(S.viewData.available, S.quantity + 1);
            await render();
            return;
        case 'quantity-minus':
            S.quantity = Math.max(1, S.quantity - 1);
            await render();
            return;
        case 'buy-now':
            S.checkout = [{ sku_id: Number(id), quantity: S.quantity }];
            S.method = 'pickup';
            S.couponId = null;
            sessionStorage.setItem('jm-checkout', JSON.stringify(S.checkout));
            go('checkout');
            return;
        case 'favorite':
            await api('/favorites/' + id, 'PUT');
            await render();
            toast('收藏已更新');
            return;
        case 'cart-plus':
        case 'cart-minus':
        case 'cart-remove': {
            const item = S.cart.items.find(i => i.id === Number(id));
            await api('/cart', 'PUT', { sku_id: item.id, quantity: action === 'cart-remove' ? 0 : item.quantity + (action === 'cart-plus' ? 1 : -1), selected: !!item.selected });
            await render();
            return;
        }
        case 'checkout':
            S.checkout = S.cart.items.filter(i => i.selected && i.valid).map(i => ({ sku_id: i.id, quantity: i.quantity }));
            S.method = 'pickup';
            S.couponId = null;
            sessionStorage.setItem('jm-checkout', JSON.stringify(S.checkout));
            go('checkout');
            return;
        case 'method':
            S.method = el.dataset.method;
            await render();
            return;
        case 'place-order': {
            if (!S.quote)
                return;
            const o = await api('/orders', 'POST', { quote_id: S.quote.id }, S.checkoutKey);
            S.checkout = null;
            sessionStorage.removeItem('jm-checkout');
            go('order', { id: o.id });
            toast('订单已创建，商品已预留');
            return;
        }
        case 'pay':
            modal('模拟微信支付', `<div class="pay-modal">${icon('shield')}<p style="margin-top:12px">京漫便民 · 本地模拟商户</p>${amount(S.viewData.total_cents)}<span class="pill amber">不会连接微信钱包 · 不真实扣款</span></div><div class="row"><button class="button primary grow" data-action="pay-confirm" data-id="${id}">确认模拟付款</button><button class="button outline" data-action="pay-fail" data-id="${id}">模拟失败</button></div>`);
            return;
        case 'pay-confirm':
            await api('/lab/pay/' + id, 'POST', {});
            closeModal();
            await render();
            toast('模拟支付成功，等待门店接单');
            return;
        case 'pay-fail':
            try {
                await api('/lab/pay/' + id, 'POST', { success: false });
            }
            finally {
                closeModal();
                await render();
            }
            return;
        case 'cancel-order':
            modal('确认取消订单', `<p>未付款会释放预占库存；付款后取消将创建模拟退款任务。配送开始后取消扣2元配送费，实物退回需门店核对。已付款自提订单可保留至核销或取消。</p><div class="row" style="margin-top:22px">${button('确认取消', 'cancel-confirm', 'danger', `data-id="${id}"`)}${button('再想一想', 'close', 'outline')}</div>`);
            return;
        case 'cancel-confirm':
            await api('/orders/' + id + '/cancel', 'POST', {});
            closeModal();
            await render();
            toast('取消操作已提交');
            return;
        case 'accept':
            await api('/admin/orders/' + id + '/accept', 'POST', {});
            await render();
            toast('已接单，开始拣货');
            return;
        case 'pick-line': {
            const line = S.viewData.items.find(i => i.id === Number(el.dataset.line));
            await api('/admin/orders/' + oid + '/pick', 'POST', { line_id: line.id, quantity: line.quantity - line.shortage_qty });
            await render();
            return;
        }
        case 'pick-all':
            for (const line of S.viewData.items)
                await api('/admin/orders/' + id + '/pick', 'POST', { line_id: line.id, quantity: line.quantity - line.shortage_qty });
            await render();
            toast('已确认全部商品拣齐');
            return;
        case 'shortage': {
            const line = S.viewData.items.find(i => i.id === Number(el.dataset.line));
            modal('登记缺货退款', `<p>${e(line.name)}，登记缺货1件。退款按照优惠分摊后的实际支付金额计算，不会把不存在的实物补回库存。</p><div style="margin-top:20px">${button('确认缺货并申请退款', 'shortage-confirm', 'danger', `data-id="${oid}" data-line="${line.id}" data-key="${uniqueKey('shortage')}"`)}</div>`);
            return;
        }
        case 'shortage-confirm':
            await api('/admin/orders/' + id + '/shortage', 'POST', { line_id: Number(el.dataset.line), quantity: 1 }, el.dataset.key);
            closeModal();
            await render();
            toast('已登记缺货，退款任务已创建');
            return;
        case 'ready':
            await api('/admin/orders/' + id + '/ready', 'POST', {});
            await render();
            toast('已完成打包');
            return;
        case 'pickup':
            modal('核销自提订单', `<form data-form="pickup" data-id="${id}"><p>请向顾客获取6位核销码。</p><div class="field"><label>自提核销码</label><input name="code" pattern="[0-9]{6}" maxlength="6" inputmode="numeric" placeholder="输入顾客出示的核销码" required></div><button class="button primary full">确认核销</button></form>`);
            return;
        case 'dispatch':
            await api('/admin/orders/' + id + '/dispatch', 'POST', {});
            await render();
            toast('已呼叫模拟骑手');
            return;
        case 'advance-delivery':
            await api('/lab/delivery/' + id + '/' + el.dataset.state, 'POST', {});
            await render();
            toast('配送状态已更新');
            return;
        case 'aftersale':
            modal('申请售后退款', `<form data-form="aftersale" data-id="${id}" data-key="${uniqueKey('aftersale')}"><p>本次申请退还订单剩余实付金额，由店长审核；不会自动增加实物库存。</p><div class="field"><label>售后原因</label><textarea name="reason" minlength="2" maxlength="200" required placeholder="请描述遇到的问题"></textarea></div><button class="button primary full">提交售后申请</button></form>`);
            return;
        case 'approve-refund':
        case 'reject-refund':
            await api('/admin/refunds/' + id + '/approve', 'POST', { approve: action === 'approve-refund' });
            await render();
            toast('售后申请已处理');
            return;
        case 'quick':
            if (el.dataset.page === 'receipts') {
                await perform('receipts', el);
                return;
            }
            go(el.dataset.page);
            return;
        case 'stock-edit': {
            const p = S.products.find(p => p.id === Number(id));
            modal('库存调整 · ' + e(p.name), `<form data-form="inventory" data-id="${id}" data-key="${uniqueKey('inventory')}"><p>账面 ${p.on_hand} · 预占 ${p.reserved} · 可售 ${p.available}</p><div class="field"><label>调整类型</label><select name="reason"><option value="purchase">采购入库</option><option value="writeoff">损耗报损</option><option value="pos_sale">模拟 POS 销售出库</option><option value="return">退货实物验收入库</option></select></div><div class="field"><label>数量（正整数）</label><input name="quantity" type="number" min="1" max="10000" step="1" value="5" required></div><button class="button primary full">确认并写入库存流水</button></form>`);
            return;
        }
        case 'price-edit': {
            const p = S.products.find(p => p.id === Number(id));
            modal('修改售价 · ' + e(p.name), `<form data-form="price" data-id="${id}" data-version="${p.version}"><div class="field"><label>售价（元）</label><input name="price" value="${money(p.price_cents)}" inputmode="decimal" required></div><p class="footnote">已有订单价格快照不受影响。尚未提交的旧报价会失效。</p><button class="button primary full" style="margin-top:20px">保存售价</button></form>`);
            return;
        }
        case 'toggle-product': {
            const p = S.products.find(p => p.id === Number(id));
            await api('/admin/products/' + id, 'PATCH', { version: p.version, active: !p.active });
            await render();
            toast(p.active ? '商品已下架' : '商品已上架');
            return;
        }
        case 'product-new':
            modal('新增门店商品', `<form data-form="product"><div class="field"><label>商品名称</label><input name="name" maxlength="60" minlength="2" required placeholder="例如：鲜切花束"></div><div class="field-row"><div class="field"><label>商品分类</label><select name="category">${S.categories.map(c => `<option value="${c.id}">${e(c.name)}</option>`).join('')}</select></div><div class="field"><label>规格</label><input name="unit" value="1份" required maxlength="30"></div></div><div class="field-row"><div class="field"><label>售价（元）</label><input name="price" inputmode="decimal" value="9.90" required></div><div class="field"><label>初始入库</label><input name="quantity" type="number" min="0" max="10000" step="1" value="20" required></div></div><div class="field"><label>商品条码（8–14位）</label><input name="barcode" pattern="[0-9]{8,14}" inputmode="numeric" required></div><button class="button primary full">创建商品</button></form>`);
            return;
        case 'stock-ledger': {
            const rows = await api('/admin/stock-ledger');
            modal('库存流水', `<p>只追加、不覆盖。最近${rows.length}条记录。</p><pre>${e(rows.slice(0, 35).map(r => `${timeLabel(r.created)} SKU${r.sku_id} ${r.reason}\n账面 ${r.delta_hand > 0 ? '+' : ''}${r.delta_hand} / 预占 ${r.delta_reserved > 0 ? '+' : ''}${r.delta_reserved}`).join('\n\n'))}</pre>`);
            return;
        }
        case 'receipts': {
            const rows = await api('/admin/print-receipts');
            modal('模拟小票记录', rows.length ? rows.slice(0, 10).map(r => `<pre>${e(r.body)}</pre>`).join('') : '<p>还没有成功打印的小票。订单付款后驱动任务队列即可生成。</p>');
            return;
        }
        case 'fault':
            await api('/lab/switch', 'PUT', { key: el.dataset.key, enabled: !S.viewData.lab.switches[el.dataset.key] });
            await render();
            return;
        case 'worker': {
            const result = await api('/lab/worker', 'POST', {});
            await render();
            toast(`处理 ${result.processed} 条任务，完成 ${result.done} 条，失败 ${result.failed} 条`);
            return;
        }
        case 'sample-order': {
            await api('/lab/sample-order', 'POST', {}, uniqueKey('sample'));
            await render();
            toast('演练订单已创建并模拟付款，可去门店接单');
            return;
        }
        case 'export': {
            const report = await api('/admin/export');
            const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }), url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'jingman-reconciliation.json';
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            toast('对账数据已导出');
            return;
        }
        case 'address-new':
            addressModal();
            return;
        case 'address-edit': {
            const addresses = await api('/addresses');
            addressModal(addresses.find(a => a.id === Number(id)));
            return;
        }
        case 'address-delete':
            await api('/addresses/' + id, 'DELETE');
            await render();
            toast('地址已删除，历史订单快照不受影响');
            return;
        case 'locate':
            if (!navigator.geolocation) {
                toast('当前环境不提供定位，请手动填写地址坐标');
                return;
            }
            navigator.geolocation.getCurrentPosition(position => { const f = overlay.querySelector('form'); if (f) {
                f.elements.latitude.value = position.coords.latitude;
                f.elements.longitude.value = position.coords.longitude;
            } toast('坐标已填写，请确认详细地址'); }, () => toast('没有取得定位授权，仍然可以手动填写地址'));
            return;
        case 'profile-link': {
            const p = el.dataset.page;
            if (['addresses', 'coupons', 'favorites'].includes(p)) {
                go(p);
                return;
            }
            if (p === 'notifications') {
                const notes = await api('/notifications');
                modal('消息通知', notes.map(n => `<div class="job"><b>${e(n.message)}</b><small>${timeLabel(n.created)}</small></div>`).join('') || '<p>目前没有新的订单通知。</p>');
                return;
            }
            modal(p === 'support' ? '联系门店' : '关于京漫便民', S.store.local_preview ? `<p>${e(S.store.name)}</p><p>${e(S.store.address)}</p><p>电话：${e(S.store.phone)} · 营业时间 ${e(S.store.hours)}</p><p>${e(S.store.notice)}</p><p>本地模拟支付，不实际扣款。</p>` : `<p>京漫便民本地联调系统，支付和履约为模拟。</p>`);
            return;
        }
        case 'coupon-new':
            modal('发放优惠券', `<form data-form="coupon"><div class="field"><label>演练顾客</label><select name="user"><option value="1">小雨同学</option><option value="2">另一位顾客</option></select></div><div class="field-row"><div class="field"><label>使用门槛（元）</label><input name="minimum" value="30.00" required inputmode="decimal"></div><div class="field"><label>优惠金额（元）</label><input name="discount" value="3.00" required inputmode="decimal"></div></div><button class="button primary full">发放到顾客账户</button></form>`);
            return;
        case 'category-new':
            modal('新增商品分类', `<form data-form="category"><div class="field"><label>分类名称</label><input name="name" minlength="2" maxlength="30" required></div><button class="button primary full">创建分类</button></form>`);
            return;
    }
}
document.addEventListener('click', event => { const el = event.target.closest('[data-action]'); if (!el)
    return; event.preventDefault(); safe(() => perform(el.dataset.action, el), el); });
document.addEventListener('change', event => { const el = event.target; if (!el.dataset.change)
    return; safe(async () => { switch (el.dataset.change) {
    case 'persona':
        await persona(el.value);
        break;
    case 'cart-select': {
        const item = S.cart.items.find(i => i.id === Number(el.dataset.id));
        await api('/cart', 'PUT', { sku_id: item.id, quantity: item.quantity, selected: el.checked });
        await render();
        break;
    }
    case 'coupon-select':
        S.couponId = Number(el.value) || null;
        await render();
        break;
    case 'address-select':
        S.addressId = Number(el.value) || null;
        await render();
        break;
} }); });
document.addEventListener('submit', event => {
    const form = event.target;
    if (!form.dataset.form)
        return;
    event.preventDefault();
    const data = new FormData(form), buttonEl = event.submitter;
    safe(async () => {
        const value = k => String(data.get(k) || '');
        switch (form.dataset.form) {
            case 'fulfillment': {
                const p = S.products.find(p => p.id === Number(form.dataset.id));
                await api('/admin/products/' + form.dataset.id + '/fulfillment', 'PATCH', {version: Number(form.dataset.version), weight_g: value('weight') === '' ? null : Number(value('weight')), pickup_only: p.fulfillment_note ? !!p.pickup_only : value('channel') === 'pickup'});
                closeModal(); await render(); toast('配送资料已保存，旧报价会重新校验'); break;
            }
            case 'login':
                S.key = value('key').trim();
                await login('customer');
                go('home');
                await render();
                break;
            case 'search':
                go(form.dataset.target || 'categories', { q: value('q').trim() });
                break;
            case 'address': {
                const body = { name: value('name'), mobile: value('mobile'), address: value('address'), latitude: Number(value('latitude')), longitude: Number(value('longitude')) };
                await api('/addresses' + (form.dataset.id ? '/' + form.dataset.id : ''), form.dataset.id ? 'PUT' : 'POST', body);
                closeModal();
                await render();
                toast('地址已保存');
                break;
            }
            case 'pickup':
                await api('/admin/orders/' + form.dataset.id + '/pickup', 'POST', { code: value('code') });
                closeModal();
                await render();
                toast('核销成功，订单已完成');
                break;
            case 'aftersale':
                await api('/orders/' + form.dataset.id + '/aftersale', 'POST', { reason: value('reason') }, form.dataset.key);
                closeModal();
                await render();
                toast('售后申请已提交，等待店长审核');
                break;
            case 'inventory': {
                const reason = value('reason'), n = Number(value('quantity'));
                await api('/admin/inventory/adjust', 'POST', { sku_id: Number(form.dataset.id), delta: ['writeoff', 'pos_sale'].includes(reason) ? -n : n, reason }, form.dataset.key);
                closeModal();
                await render();
                toast('库存与流水已同步更新');
                break;
            }
            case 'price':
                await api('/admin/products/' + form.dataset.id, 'PATCH', { version: Number(form.dataset.version), price_cents: yuanToFen(value('price')) });
                closeModal();
                await render();
                toast('商品售价已更新');
                break;
            case 'product':
                await api('/admin/products', 'POST', { name: value('name'), category_id: Number(value('category')), unit: value('unit'), price_cents: yuanToFen(value('price')), quantity: Number(value('quantity')), barcode: value('barcode') });
                closeModal();
                await render();
                toast('商品已创建，初始入库已记账');
                break;
            case 'settings':
                await api('/admin/store', 'PATCH', { version: S.store.version, open: value('open') === '1', radius_km: Number(value('radius')), minimum_cents: yuanToFen(value('minimum')), delivery_cents: yuanToFen(value('delivery')), free_shipping_cents: yuanToFen(value('free')) });
                await render();
                toast('门店规则已保存');
                break;
            case 'delivery-rules':
                await api('/admin/delivery-rules', 'PATCH', { version: Number(form.dataset.version), start: value('start'), end: value('end'), rounding: value('rounding'), provisional_hours: !value('hours_confirmed'), provisional_rounding: !value('rounding_confirmed') });
                closeModal();
                await render();
                toast('配送规则已保存，历史订单费用不变');
                break;
            case 'coupon':
                await api('/admin/coupons', 'POST', { user_id: Number(value('user')), minimum_cents: yuanToFen(value('minimum')), discount_cents: yuanToFen(value('discount')) });
                closeModal();
                await render();
                toast('优惠券已发放');
                break;
            case 'category':
                await api('/admin/categories', 'POST', { name: value('name') });
                closeModal();
                await render();
                toast('商品分类已创建');
                break;
        }
    }, buttonEl);
});
document.addEventListener('keydown', event => { const dialog = overlay.querySelector('[role=dialog]'); if (!dialog)
    return; if (event.key === 'Escape') {
    closeModal();
    return;
} if (event.key === 'Tab') {
    const nodes = [...dialog.querySelectorAll('button,input,select,textarea,a[href]')].filter(n => !n.disabled);
    const first = nodes[0], last = nodes.at(-1);
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
    }
    else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
    }
} });
window.addEventListener('hashchange', () => render());
(async () => { try {
    if (location.hash.startsWith('#access=')) {
        S.key = decodeURIComponent(location.hash.slice(8));
        history.replaceState(null, '', '#/home');
        await login('customer');
    }
    await render();
}
catch (error) {
    S.token = '';
    renderLogin();
    toast(error.message);
} })();
