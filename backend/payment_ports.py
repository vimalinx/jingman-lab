"""Payment integration seam. Lab execution cannot instantiate a real provider.

Real adapter implementations must exchange integer-fen server-priced orders,
verify/decrypt provider callbacks and map them to business events. A frontend
payment completion callback must NEVER mark an order paid.
"""
from typing import Protocol
from .service import fail


class PaymentProvider(Protocol):
    def create_payment(self, actor: dict, order_id: str, *, success: bool = True) -> dict: ...
    def query_payment(self, actor: dict, order_id: str) -> dict: ...


class RefundProvider(Protocol):
    """Future external seam; refund tasks still use the documented lab ledger.

    amount_cents must come from the server's approved refund record. The stable
    refund_id is the upstream idempotency reference; timeout requires query,
    never creation of a new refund_id.
    """
    def request_refund(self, refund_id: str, order_id: str, amount_cents: int) -> dict: ...
    def query_refund(self, refund_id: str) -> dict: ...


class MockPaymentProvider:
    name = 'mock'

    def __init__(self, engine):
        self.engine = engine

    def create_payment(self, actor, order_id, *, success=True):
        return self.engine.gateway_charge(actor, order_id, success)

    def query_payment(self, actor, order_id):
        order = self.engine.order(actor, order_id)
        return {'provider': self.name, 'simulated': True, 'order_id': order_id,
                'paid_cents': order['paid_cents'], 'refunded_cents': order['refunded_cents'],
                'state': order['state']}


def payment_provider(engine, name='mock'):
    if name != 'mock':
        fail(503, 'payment_not_configured', '真实支付尚未接入；不会自动切换或发起扣款')
    return MockPaymentProvider(engine)
