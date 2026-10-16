"""Bounded private GCS JSON transport, not yet wired to any public API.

API protocol checked against Google's objects insert/get/delete reference, 2026-10-16.
Uses the existing private bucket; never changes its ACL, retention, versioning or IAM.
A durable application fence is REQUIRED: upload_once/delete_once do exactly one request,
and an uncertain result must be recovered by observe(), never by redispatching the write.
"""
from __future__ import annotations

import json
from hashlib import sha256
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Callable, Mapping
from urllib.parse import quote
from uuid import uuid4

import httpx

from .asset_storage import (
    AssetManifest, AssetStorageError, AssetStorageErrorCode as Code,
    DisabledAssetStorage, StoredAsset, valid_generation,
)

_ORIGIN = "https://storage.googleapis.com"
_METADATA_LIMIT = 64 * 1024
_SCOPE = "https://www.googleapis.com/auth/devstorage.read_write"


@dataclass(frozen=True, slots=True)
class GCSAssetConfig:
    bucket: str
    max_active_bytes: int
    enabled: bool = False

    def __post_init__(self):
        # Existing infra bucket names fit this conservative subset; never accept a URL/path.
        if not isinstance(self.bucket, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]", self.bucket):
            raise AssetStorageError(Code.INVALID)
        if type(self.max_active_bytes) is not int or self.max_active_bytes < 1 or type(self.enabled) is not bool:
            raise AssetStorageError(Code.INVALID)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> GCSAssetConfig | None:
        env = os.environ if env is None else env
        flag = env.get("CAMPAIA_ASSET_STORAGE_ENABLED", "false")
        if flag == "false":
            return None
        if flag != "true":
            raise AssetStorageError(Code.INVALID)
        raw = env.get("CAMPAIA_ASSET_MAX_ACTIVE_BYTES", "")
        if not re.fullmatch(r"[1-9][0-9]{0,18}", raw):
            raise AssetStorageError(Code.INVALID)
        return cls(env.get("CAMPAIA_ASSET_BUCKET", ""), int(raw), enabled=True)


class LazyGoogleToken:
    """ADC is accessed only on an explicitly enabled operation, never import/bootstrap."""
    def __init__(self):
        self._credentials = None
        self._lock = threading.Lock()

    def __call__(self) -> str:
        try:
            import google.auth
            from google.auth.transport.requests import Request

            with self._lock:
                if self._credentials is None:
                    self._credentials, _ = google.auth.default(scopes=[_SCOPE])
                if not self._credentials.valid:
                    self._credentials.refresh(Request())
                token = self._credentials.token
                if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
                    raise ValueError("invalid token")
                return token
        except Exception:
            # Never include provider errors, credential paths, response bodies or tokens.
            raise AssetStorageError(Code.AUTH) from None


@dataclass
class GCSAssetStorage:
    config: GCSAssetConfig
    token_provider: Callable[[], str] = field(default_factory=LazyGoogleToken, repr=False)
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    mode = "PROVIDER"

    @property
    def namespace(self) -> str:
        return "gcs:" + sha256(self.config.bucket.encode()).hexdigest()

    @property
    def max_active_bytes(self) -> int:
        return self.config.max_active_bytes

    def _headers(self) -> dict[str, str]:
        if not self.config.enabled:
            raise AssetStorageError(Code.DISABLED)
        try:
            token = self.token_provider()
            if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
                raise ValueError("invalid token")
            return {"Authorization": f"Bearer {token}", "Accept-Encoding": "identity"}
        except Exception:
            raise AssetStorageError(Code.AUTH) from None

    def _path(self, manifest: AssetManifest) -> str:
        return f"/storage/v1/b/{self.config.bucket}/o/{quote(manifest.identity.object_name, safe='')}"

    def _request(self, method: str, path: str, *, params: dict[str, str],
                 limit: int, body: bytes | None = None, content_type: str | None = None,
                 mutation: bool = False, missing: bool = False) -> bytes | None:
        headers = self._headers()
        if content_type:
            headers["Content-Type"] = content_type
        try:
            with httpx.Client(transport=self.transport, timeout=15.0, follow_redirects=False,
                              trust_env=False) as client:
                with client.stream(method, _ORIGIN + path, params=params,
                                   headers=headers, content=body) as response:
                    status = response.status_code
                    if status == 404 and missing:
                        return None
                    if status in (401, 403):
                        raise AssetStorageError(Code.AUTH)
                    if status in (409, 412):
                        raise AssetStorageError(Code.CONFLICT)
                    if not 200 <= status < 300:
                        raise AssetStorageError(Code.UNCERTAIN if mutation else Code.UNAVAILABLE)
                    # No transparent decompression / zip bombs, redirects or arbitrary hosts.
                    if response.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
                        raise AssetStorageError(Code.UNCERTAIN if mutation else Code.INTEGRITY)
                    raw_length = response.headers.get("Content-Length")
                    if raw_length is not None and (not raw_length.isascii() or not raw_length.isdecimal() or int(raw_length) > limit):
                        raise AssetStorageError(Code.UNCERTAIN if mutation else Code.INTEGRITY)
                    chunks = bytearray()
                    for chunk in response.iter_bytes(chunk_size=16 * 1024):
                        if len(chunks) + len(chunk) > limit:
                            raise AssetStorageError(Code.UNCERTAIN if mutation else Code.INTEGRITY)
                        chunks.extend(chunk)
                    return bytes(chunks)
        except AssetStorageError:
            raise
        except Exception:
            # A timed-out mutation may have succeeded. No automatic HTTP retry.
            raise AssetStorageError(Code.UNCERTAIN if mutation else Code.UNAVAILABLE) from None

    @staticmethod
    def _json(raw: bytes | None) -> dict:
        try:
            result = json.loads(raw)
            if type(result) is not dict:
                raise ValueError("metadata must be an object")
            return result
        except (ValueError, TypeError, UnicodeError):
            raise AssetStorageError(Code.INTEGRITY) from None

    def _verified(self, raw: bytes | None, expected: AssetManifest,
                  generation: str | None = None) -> StoredAsset:
        data = self._json(raw)
        try:
            observed_generation = valid_generation(data.get("generation"))
        except AssetStorageError:
            raise AssetStorageError(Code.INTEGRITY) from None
        if (
            data.get("bucket") != self.config.bucket
            or data.get("name") != expected.identity.object_name
            or data.get("contentType") != "image/png"
            or data.get("contentEncoding") not in (None, "", "identity")
            or data.get("size") != str(expected.size)
            or data.get("md5Hash") != expected.md5_base64
            or data.get("cacheControl") != "private, no-store"
            or data.get("metadata") != expected.identity.tags(expected.sha256)
            or (generation is not None and observed_generation != generation)
        ):
            raise AssetStorageError(Code.INTEGRITY)
        return StoredAsset(expected, observed_generation)

    def upload_once(self, manifest: AssetManifest, data: bytes) -> StoredAsset:
        manifest.verify_bytes(data)  # Invalid input fails before token discovery.
        if manifest.size > self.config.max_active_bytes:
            raise AssetStorageError(Code.INVALID)
        boundary = "campaia_" + uuid4().hex
        metadata = {
            "name": manifest.identity.object_name, "contentType": "image/png",
            "cacheControl": "private, no-store", "md5Hash": manifest.md5_base64,
            "metadata": manifest.identity.tags(manifest.sha256),
        }
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + json.dumps(metadata, separators=(",", ":")).encode()
            + f"\r\n--{boundary}\r\nContent-Type: image/png\r\n\r\n".encode()
            + data + f"\r\n--{boundary}--\r\n".encode()
        )
        raw = self._request("POST", f"/upload/storage/v1/b/{self.config.bucket}/o",
                            params={"uploadType": "multipart", "ifGenerationMatch": "0"},
                            limit=_METADATA_LIMIT, body=body,
                            content_type=f"multipart/related; boundary={boundary}", mutation=True)
        # Invalid success metadata also leaves the caller's durable fence unresolved.
        return self._verified(raw, manifest)

    def observe(self, manifest: AssetManifest, generation: str | None = None) -> StoredAsset | None:
        params = {"projection": "noAcl"}
        if generation is not None:
            params["generation"] = valid_generation(generation)
        raw = self._request("GET", self._path(manifest), params=params,
                            limit=_METADATA_LIMIT, missing=True)
        return None if raw is None else self._verified(raw, manifest, generation)

    def read(self, asset: StoredAsset) -> bytes:
        # Both metadata and bytes are pinned; never silently follow a replacement.
        observed = self.observe(asset.manifest, asset.generation)
        if observed is None:
            raise AssetStorageError(Code.INTEGRITY)
        raw = self._request("GET", self._path(asset.manifest),
                            params={"alt": "media", "generation": asset.generation,
                                    "ifGenerationMatch": asset.generation},
                            limit=asset.manifest.size)
        asset.manifest.verify_bytes(raw)
        return raw

    def delete_once(self, asset: StoredAsset) -> None:
        # Success means the request was accepted, not permanent erasure / retention expiry.
        # A caller must tombstone access first and observe afterward; never retry uncertain DELETE.
        self._request("DELETE", self._path(asset.manifest),
                      params={"generation": asset.generation, "ifGenerationMatch": asset.generation},
                      limit=_METADATA_LIMIT, mutation=True)


def configured_asset_storage(env: Mapping[str, str] | None = None):
    config = GCSAssetConfig.from_env(env)
    return DisabledAssetStorage() if config is None else GCSAssetStorage(config)
