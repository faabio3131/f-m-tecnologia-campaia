from __future__ import annotations

import unittest
from campaia_core.payment_urls import safe_asaas_invoice_url


class HostedInvoiceUrlTests(unittest.TestCase):
    def test_accepts_only_provider_invoice_in_matching_environment(self):
        for mode, host in [('SANDBOX', 'sandbox.asaas.com'), ('PRODUCTION', 'www.asaas.com')]:
            url = f'https://{host}/i/080225913252'
            self.assertEqual(safe_asaas_invoice_url(url, mode), url)

    def test_rejects_untrusted_urls_and_unknown_modes(self):
        for url in [None, '', 'javascript:alert(1)', 'http://sandbox.asaas.com/i/abc',
                    'https://sandbox.asaas.com.evil.test/i/abc',
                    'https://sandbox.asaas.com@evil.test/i/abc',
                    'https://evil.test@sandbox.asaas.com/i/abc',
                    'https://sandbox.asaas.com:443/i/abc',
                    'https://sandbox.asaas.com/i/abc?redirect=https://evil.test',
                    'https://sandbox.asaas.com/i/abc#fragment',
                    'https://sandbox.asaas.com/i/%2e%2e',
                    'https://sandbox.asaas.com/i/abc\n',
                    'https://www.asaas.com/i/abc']:
            with self.subTest(url=url):
                self.assertIsNone(safe_asaas_invoice_url(url, 'SANDBOX'))
        self.assertIsNone(safe_asaas_invoice_url('https://sandbox.asaas.com/i/abc', 'SIMULATOR'))
