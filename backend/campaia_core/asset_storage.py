"""Private asset storage primitives; authorization and durable dispatch belong to the API.

These are internal transport types, NOT an upload endpoint or image decoder. Callers must
normalize/validate images and persist the dispatch fence before any storage mutation.
No public URLs, user filenames, caller-selected object paths or automatic retries.
"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol
from uuid import UUID

MAX_ASSET_BYTES = 5 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class AssetStorageErrorCode(str, Enum):
    DISABLED = "DISABLED"
    INVALID = "INVALID"
    AUTH = "AUTH"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"
    UNCERTAIN = "UNCERTAIN"
    INTEGRITY = "INTEGRITY"


class AssetStorageError(Exception):
    def __init__(self, code: AssetStorageErrorCode):
        self.code = code
        super().__init__(code.value)


def _invalid() -> None:
    raise AssetStorageError(AssetStorageErrorCode.INVALID)


def _owner(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        _invalid()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_generation(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,24}", value):
        _invalid()
    return value


@dataclass(frozen=True, slots=True)
class AssetIdentity:
    tenant_id: str = field(repr=False)
    brand_profile_id: str = field(repr=False)
    asset_id: str

    def __post_init__(self):
        _owner(self.tenant_id)
        _owner(self.brand_profile_id)
        try:
            if not isinstance(self.asset_id, str) or str(UUID(self.asset_id)) != self.asset_id:
                _invalid()
        except (ValueError, AttributeError):
            _invalid()

    @property
    def object_name(self) -> str:
        return f"brand/v1/{_owner(self.tenant_id)}/{_owner(self.brand_profile_id)}/{self.asset_id}.png"

    def tags(self, sha256: str) -> dict[str, str]:
        return {
            "campaia_schema": "brand_asset_v1",
            "tenant_sha256": _owner(self.tenant_id),
            "brand_sha256": _owner(self.brand_profile_id),
            "asset_id": self.asset_id,
            "sha256": sha256,
        }


@dataclass(frozen=True, slots=True)
class AssetManifest:
    """Expected facts persisted by the caller before upload, independently of GCS."""
    identity: AssetIdentity
    size: int
    sha256: str
    md5_base64: str

    def __post_init__(self):
        if not isinstance(self.identity, AssetIdentity):
            _invalid()
        if type(self.size) is not int or not 8 < self.size <= MAX_ASSET_BYTES:
            _invalid()
        if not isinstance(self.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            _invalid()
        try:
            raw = base64.b64decode(self.md5_base64, validate=True)
            if len(raw) != 16 or base64.b64encode(raw).decode("ascii") != self.md5_base64:
                _invalid()
        except (ValueError, TypeError):
            _invalid()

    @classmethod
    def from_normalized_png(cls, identity: AssetIdentity, data: bytes) -> AssetManifest:
        # Signature is only a transport invariant, never a substitute for image decoding.
        if type(data) is not bytes or not 8 < len(data) <= MAX_ASSET_BYTES or not data.startswith(PNG_SIGNATURE):
            _invalid()
        return cls(identity, len(data), hashlib.sha256(data).hexdigest(),
                   base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode("ascii"))

    def verify_bytes(self, data: bytes) -> None:
        if type(data) is not bytes or len(data) != self.size or not data.startswith(PNG_SIGNATURE):
            raise AssetStorageError(AssetStorageErrorCode.INTEGRITY)
        if hashlib.sha256(data).hexdigest() != self.sha256:
            raise AssetStorageError(AssetStorageErrorCode.INTEGRITY)
        if base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode("ascii") != self.md5_base64:
            raise AssetStorageError(AssetStorageErrorCode.INTEGRITY)


@dataclass(frozen=True, slots=True)
class StoredAsset:
    manifest: AssetManifest
    generation: str

    def __post_init__(self):
        if not isinstance(self.manifest, AssetManifest):
            _invalid()
        valid_generation(self.generation)


class PrivateAssetStorage(Protocol):
    def upload_once(self, manifest: AssetManifest, data: bytes) -> StoredAsset: ...
    def observe(self, manifest: AssetManifest, generation: str | None = None) -> StoredAsset | None: ...
    def read(self, asset: StoredAsset) -> bytes: ...
    def delete_once(self, asset: StoredAsset) -> None: ...


class DisabledAssetStorage:
    """Default capability. Construction/import never discovers credentials or sends HTTP."""
    def upload_once(self, manifest: AssetManifest, data: bytes) -> StoredAsset:
        raise AssetStorageError(AssetStorageErrorCode.DISABLED)

    def observe(self, manifest: AssetManifest, generation: str | None = None) -> StoredAsset | None:
        raise AssetStorageError(AssetStorageErrorCode.DISABLED)

    def read(self, asset: StoredAsset) -> bytes:
        raise AssetStorageError(AssetStorageErrorCode.DISABLED)

    def delete_once(self, asset: StoredAsset) -> None:
        raise AssetStorageError(AssetStorageErrorCode.DISABLED)
