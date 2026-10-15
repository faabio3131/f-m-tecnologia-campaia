"""Read projections must not make pre-WP-R02 financial records undecodable on rollback."""
from dataclasses import dataclass, fields, replace
from datetime import datetime, timezone
from decimal import Decimal
import unittest

from api.db import encode, decode
from campaia_core.payment_gateway import ChargeResult, GatewayChargeStatus, GatewayMode
from campaia_core.subscription import SubscriptionCharge, ChargeLineItem


@dataclass
class PreviousChargeResult:
    gateway_charge_id: str
    status: object
    provider: str
    mode: object


@dataclass
class PreviousSubscriptionCharge:
    billing_id: str
    tenant_id: str
    customer_ref: str
    customer_document: str
    competence: str
    currency: str
    line_items: tuple
    status: object
    plan_id: str | None
    purpose: object


class BillingRecordCompatibilityTests(unittest.TestCase):
    def test_old_constructor_fields_unchanged_and_new_read_preserves_observations(self):
        charge = SubscriptionCharge('bill', 'tenant', 'customer', '11144477735', '2026-10', 'BRL',
                                    (ChargeLineItem('subscription', Decimal('10.50')),))
        charge = replace(charge, created_at=datetime.now(timezone.utc), gateway_status='CONFIRMED',
                         gateway_provider='ASAAS', gateway_mode='SANDBOX',
                         invoice_url='https://sandbox.asaas.com/i/test')
        result = ChargeResult('pay', GatewayChargeStatus.PENDING, 'ASAAS', GatewayMode.SANDBOX,
                              'https://sandbox.asaas.com/i/test')
        for value, previous_type in [(charge, PreviousSubscriptionCharge), (result, PreviousChargeResult)]:
            encoded = encode(value)
            # Previous api.db.decode passes ONLY the fields map to cls(**fields).
            old_kwargs = {key: decode(data) for key, data in encoded['fields'].items()}
            self.assertEqual(set(old_kwargs), {field.name for field in fields(previous_type)})
            old_record = previous_type(**old_kwargs)
            self.assertIsNotNone(old_record)
            self.assertEqual(decode(encoded), value)
            legacy = {key: data for key, data in encoded.items() if key != 'billing_observations'}
            self.assertIsNone(decode(legacy).invoice_url)

    def test_observations_cannot_override_financial_or_tenant_fields(self):
        value = ChargeResult('pay', GatewayChargeStatus.PENDING, 'ASAAS', GatewayMode.SANDBOX)
        encoded = encode(value)
        encoded['billing_observations']['tenant_id'] = 'other'
        with self.assertRaises(ValueError):
            decode(encoded)
