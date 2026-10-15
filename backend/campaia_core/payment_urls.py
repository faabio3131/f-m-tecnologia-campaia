"""Hosted Asaas invoice URLs: only provider-returned, exact environment and path.

No fetching, redirects, tenant-specific hosts or synthesized payment links.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from .payment_gateway import GatewayMode


def safe_asaas_invoice_url(value: object, mode: str | GatewayMode | None) -> str | None:
    hosts = {
        GatewayMode.SANDBOX: frozenset({"sandbox.asaas.com"}),
        GatewayMode.PRODUCTION: frozenset({"www.asaas.com"}),
    }.get(mode, frozenset())
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme != "https" or url.netloc not in hosts
                or url.query or url.fragment
                or not re.fullmatch(r"/i/[A-Za-z0-9_-]+", url.path)):
            return None
    except ValueError:
        return None
    return value
