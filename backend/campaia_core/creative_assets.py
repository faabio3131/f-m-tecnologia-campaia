"""Private generated-creative identity and immutable delivery manifest.

WP-R04-04B foundation: no network, no credential resolution, no enabled storage,
no commercial credit deduction. Durable claim/dispatch/settlement belongs to F3.
Do not reuse brand asset paths: creative scope includes campaign and version.
"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from .asset_images import verify_normalized_png
from .asset_storage import MAX_ASSET_BYTES, AssetStorageError, AssetStorageErrorCode


class CreativeState(StrEnum):
    RESERVED = "RESERVED"
    GENERATING = "GENERATING"
    STORAGE_PENDING = "STORAGE_PENDING"
    STORED = "STORED"
    FAILED = "FAILED"
    DELETE_PENDING = "DELETE_PENDING"
    DELETED = "DELETED"


def _invalid() -> None:
    raise AssetStorageError(AssetStorageErrorCode.INVALID)


def _hash_scope(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 256 or not value.strip():
        _invalid()
    try:
        raw = value.encode("utf-8", errors="strict")
    except UnicodeError:
        _invalid()
    return hashlib.sha256(raw).hexdigest()


def _uuid(value: str) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            _invalid()
    except (ValueError, AttributeError, TypeError):
        _invalid()
    return value


@dataclass(frozen=True, slots=True)
class CreativeIdentity:
    """All scopes are server-authoritative, never inferred from request object keys."""
    tenant_id: str = field(repr=False)
    business_unit_id: str = field(repr=False)
    campaign_id: str = field(repr=False)
    campaign_version: int
    creative_id: str

    def __post_init__(self) -> None:
        for value in (self.tenant_id, self.business_unit_id, self.campaign_id):
            _hash_scope(value)
        if type(self.campaign_version) is not int or not 1 <= self.campaign_version <= 2**31 - 1:
            _invalid()
        _uuid(self.creative_id)

    @property
    def object_name(self) -> str:
        return (f"creative/v1/{_hash_scope(self.tenant_id)}/"
                f"{_hash_scope(self.business_unit_id)}/{_hash_scope(self.campaign_id)}/"
                f"{self.campaign_version}/{self.creative_id}.png")


@dataclass(frozen=True, slots=True)
class CreativeManifest:
    identity: CreativeIdentity
    sha256: str
    size: int
    width: int
    height: int
    provider: str
    model: str
    generation_request_id: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, CreativeIdentity):
            _invalid()
        if not isinstance(self.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            _invalid()
        if type(self.size) is not int or not 8 < self.size <= MAX_ASSET_BYTES:
            _invalid()
        if any(type(n) is not int or not 1 <= n <= 8192 for n in (self.width, self.height)):
            _invalid()
        if self.width * self.height > 4194304:
            _invalid()
        for name in (self.provider, self.model):
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name):
                _invalid()
        _hash_scope(self.generation_request_id)

    @classmethod
    def from_normalized_png(cls, identity: CreativeIdentity, png: bytes, *,
                            provider: str, model: str, generation_request_id: str) -> CreativeManifest:
        checked = verify_normalized_png(png)
        return cls(identity=identity, sha256=hashlib.sha256(png).hexdigest(),
                   size=len(png), width=checked.width, height=checked.height,
                   provider=provider, model=model, generation_request_id=generation_request_id)

    def verify(self, png: bytes) -> None:
        checked = verify_normalized_png(png)
        if (len(png) != self.size or hashlib.sha256(png).hexdigest() != self.sha256
                or (checked.width, checked.height) != (self.width, self.height)):
            raise AssetStorageError(AssetStorageErrorCode.INTEGRITY)

    def storage_metadata(self) -> dict[str, str]:
        return {
            "campaia_schema": "generated_creative_v1",
            "tenant_sha256": _hash_scope(self.identity.tenant_id),
            "unit_sha256": _hash_scope(self.identity.business_unit_id),
            "campaign_sha256": _hash_scope(self.identity.campaign_id),
            "campaign_version": str(self.identity.campaign_version),
            "creative_id": self.identity.creative_id,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class CreativeStoredProof:
    """Only provider-confirmed immutable object generations count as stored."""
    manifest: CreativeManifest
    storage_generation: str
    def __post_init__(self) -> None:
        if not isinstance(self.manifest, CreativeManifest):
            _invalid()
        if not isinstance(self.storage_generation, str) or not re.fullmatch(
                r"[1-9][0-9]{0,24}", self.storage_generation):
            _invalid()


__all__ = ["CreativeIdentity", "CreativeManifest", "CreativeStoredProof", "CreativeState"]
