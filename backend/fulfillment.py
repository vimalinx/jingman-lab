"""Merchant delivery terms. Weights are confirmed grams per purchasable unit."""
from datetime import datetime, timedelta, timezone

DEFAULT_RULES = {
    'start': '07:30', 'end': '22:00', 'provisional_hours': True,
    'included_weight_g': 5000, 'extra_step_g': 1000, 'extra_step_cents': 150,
    'rounding': 'ceil_kg', 'provisional_rounding': True,
    'coupon_limit': 1,
}

def pickup_restriction(name, categories, weighed=False, price_cents=None):
    """User-specified sale channels, not a general regulatory classifier."""
    if '槟榔' in name:
        return '槟榔仅限到店自提'
    if any('散装零食' in category for category in categories) or (
        weighed and price_cents == 1980 and any('休闲食品' in category for category in categories)
    ):
        return '散装零食品类不定，仅限到店选购自提'
    return ''

def in_delivery_hours(timestamp, rules):
    local = datetime.fromtimestamp(timestamp, timezone(timedelta(hours=8)))
    minute = local.hour * 60 + local.minute
    def minutes(value):
        h, m = map(int, value.split(':'))
        return h * 60 + m
    return minutes(rules['start']) <= minute < minutes(rules['end'])

def extra_fee(weight_g, rules):
    excess = max(0, weight_g - rules['included_weight_g'])
    step = rules['extra_step_g']
    if rules['rounding'] == 'proportional':
        # Round integer fen half-up without binary floating point.
        return (excess * rules['extra_step_cents'] * 2 + step) // (2 * step)
    if rules['rounding'] != 'ceil_kg':
        raise ValueError('Unsupported delivery weight rounding')
    return ((excess + step - 1) // step) * rules['extra_step_cents']
