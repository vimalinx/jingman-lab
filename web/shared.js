/* priceFormat and phoneEncryption adapted from Tencent TDesign retail utils/util.js,
 * upstream snapshot 4280f410121c75775c4b1fd15c3849031f830cd7. MIT.
 * See licenses/tdesign-retail-LICENSE. The remaining helpers are new Jingman code.
 */
(function (root) {
    function priceFormat(price, fill = 0) {
        if (isNaN(price) || price === null || price === Infinity)
            return price;
        let value = Math.round(parseFloat(`${price}`) * 10 ** 8) / 10 ** 8;
        value = `${Math.ceil(value) / 100}`;
        if (fill > 0) {
            if (value.indexOf('.') === -1)
                value += '.';
            const n = fill - value.split('.')[1].length;
            for (let i = 0; i < n; i++)
                value += '0';
        }
        return value;
    }
    const phoneEncryption = phone => phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2');
    const money = cents => {
        if (!Number.isSafeInteger(cents))
            throw new Error('金额必须为整数分');
        return priceFormat(cents, 2);
    };
    const yuanToFen = value => {
        const s = String(value).trim();
        if (!/^\d+(\.\d{1,2})?$/.test(s))
            throw new Error('金额需为非负数，最多两位小数');
        const [whole, fraction = ''] = s.split('.');
        const n = Number(whole) * 100 + Number((fraction + '00').slice(0, 2));
        if (!Number.isSafeInteger(n))
            throw new Error('金额超出范围');
        return n;
    };
    const states = { pending_payment: '待付款', paid: '待接单', picking: '拣货中', ready: '待取货', delivering: '配送中', completed: '已完成', cancelled: '已取消', refund_pending: '退款中', refunded: '已退款' };
    const events = { 'order.created': '订单已创建', 'payment.succeeded': '模拟付款成功', 'order.accepted': '门店已接单', 'order.picked': '商品已拣货', 'order.shortage': '已登记缺货退款', 'order.ready': '门店已完成打包', 'delivery.created': '已呼叫模拟骑手', 'delivery.accepted': '骑手已接单', 'delivery.picked_up': '骑手已取货，配送中', 'delivery.delivered': '已送达', 'order.pickup_completed': '自提核销完成', 'order.cancelled': '订单已取消', 'order.expired': '订单超时关闭', 'payment.late_refund': '迟到付款，自动退款中', 'order.cancel_refund': '门店取消，退款中', 'refund.requested': '售后申请已提交', 'refund.approved': '售后申请已通过', 'refund.rejected': '售后申请未通过', 'refund.succeeded': '模拟退款到账' };
    const api = { money, yuanToFen, phoneEncryption, priceFormat, states, events };
    root.Jingman = api;
    if (typeof module !== 'undefined' && module.exports)
        module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
