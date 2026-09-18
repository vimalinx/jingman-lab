def test_new_mock_entry_and_status(h):
    o = h.order()
    h.request('POST', '/api/payments/' + o['id'] + '/simulate', {'success': True})
    h.request('POST', '/api/payments/' + o['id'] + '/simulate', {'success': True})
    status = h.request('GET', '/api/payments/' + o['id'])
    assert status['paid_cents'] == o['total_cents'] and status['simulated']
    assert len(h.sql("SELECT * FROM gateway_ledger WHERE kind='charge'")) == 1
    h.request('GET', '/api/payments/' + o['id'], who='customer2', status=404)


def test_unconfigured_real_endpoints_never_accept_money(h):
    o = h.order()
    h.request('POST', '/api/payments/' + o['id'] + '/prepay', {}, status=503)
    h.request('POST', '/api/payments/wechat/notify', {'success': True}, status=503)
    h.request('POST', '/api/payments/wechat/refund-notify', {'success': True}, status=503)
    assert h.sql('SELECT * FROM gateway_ledger') == []
    assert h.request('GET', '/api/orders/' + o['id'])['state'] == 'pending_payment'
