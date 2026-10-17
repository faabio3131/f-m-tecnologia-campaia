"""Bounded parent for the isolated image worker; no Pillow/C decoder in this process."""
from __future__ import annotations

import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
import zlib
from dataclasses import dataclass, field

from .asset_storage import MAX_ASSET_BYTES, PNG_SIGNATURE

MAX_PIXELS = 4_194_304
MAX_DIMENSION = 8192
_WORKER = Path(__file__).with_name("asset_image_worker.py").resolve()


class AssetImageError(Exception):
    def __init__(self, code="INVALID_IMAGE"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class NormalizedAssetImage:
    data: bytes = field(repr=False)
    width: int
    height: int


def verify_normalized_png(data: bytes) -> NormalizedAssetImage:
    """Check the worker envelope without decoding pixels in the API process.

    Only fresh 8-bit RGB/RGBA PNGs, with CRC-checked IHDR/IDAT/IEND and no ancillary
    metadata/trailing bytes. This is not a second image decoder / malware certification.
    """
    if type(data) is not bytes or not len(PNG_SIGNATURE) < len(data) <= MAX_ASSET_BYTES or not data.startswith(PNG_SIGNATURE):
        raise AssetImageError()
    offset, width, height, idat = 8, 0, 0, 0
    first = True
    while offset + 12 <= len(data):
        size = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(data):
            raise AssetImageError()
        body = data[offset + 8:offset + 8 + size]
        crc = int.from_bytes(data[offset + 8 + size:end], "big")
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            raise AssetImageError()
        if first:
            if kind != b"IHDR" or size != 13:
                raise AssetImageError()
            width, height = int.from_bytes(body[:4], "big"), int.from_bytes(body[4:8], "big")
            if (min(width, height) < 1 or max(width, height) > MAX_DIMENSION
                    or width * height > MAX_PIXELS or body[8] != 8
                    or body[9] not in (2, 6) or body[10:] != b"\x00\x00\x00"):
                raise AssetImageError()
            first = False
        elif kind == b"IDAT":
            idat += size
        elif kind == b"IEND":
            if size != 0 or idat == 0 or end != len(data):
                raise AssetImageError()
            return NormalizedAssetImage(data, width, height)
        else:
            raise AssetImageError()
        offset = end
    raise AssetImageError()


def _bounded_exchange(process, data: bytes, *, max_output=MAX_ASSET_BYTES, timeout=10.0):
    """Bound both pipes and wall time even if the decoder is compromised or hangs."""
    deadline = time.monotonic() + timeout
    sent = 0
    output = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            for pipe, event in ((process.stdin, selectors.EVENT_WRITE), (process.stdout, selectors.EVENT_READ)):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, event)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssetImageError("IMAGE_PROCESSING_UNAVAILABLE")
                for key, event in selector.select(min(remaining, 0.2)):
                    pipe = key.fileobj
                    if event & selectors.EVENT_WRITE:
                        try:
                            count = os.write(pipe.fileno(), data[sent:sent + 16 * 1024])
                            sent += count
                        except BrokenPipeError:
                            sent = len(data)
                        except BlockingIOError:
                            continue
                        if sent >= len(data):
                            selector.unregister(pipe)
                            pipe.close()
                    else:
                        try:
                            chunk = os.read(pipe.fileno(), 16 * 1024)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(pipe)
                            pipe.close()
                        elif len(output) + len(chunk) > max_output:
                            raise AssetImageError()
                        else:
                            output.extend(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssetImageError("IMAGE_PROCESSING_UNAVAILABLE")
        try:
            code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise AssetImageError("IMAGE_PROCESSING_UNAVAILABLE") from None
        if code == 3:
            raise AssetImageError("IMAGE_PROCESSING_UNAVAILABLE")
        if code != 0:
            raise AssetImageError()
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        for pipe in (process.stdin, process.stdout):
            if not pipe.closed:
                pipe.close()


def normalize_asset_image(data: bytes) -> NormalizedAssetImage:
    if type(data) is not bytes or not 0 < len(data) <= MAX_ASSET_BYTES:
        raise AssetImageError()
    if sys.platform != "linux":
        raise AssetImageError("IMAGE_PROCESSING_UNAVAILABLE")
    try:
        # Constant absolute script, no shell, no credentials/proxy/PYTHON* environment.
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", str(_WORKER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            close_fds=True, start_new_session=True, env={"LC_ALL": "C.UTF-8"},
        )
        raw = _bounded_exchange(process, data)
    except AssetImageError:
        raise
    except Exception:
        raise AssetImageError("IMAGE_PROCESSING_UNAVAILABLE") from None
    return verify_normalized_png(raw)


def edit_normalized_png(data: bytes, operation: str) -> NormalizedAssetImage:
    """Deterministic pixel transformation in the existing isolated decoder worker.

    Caller owns tenant authorization, revision persistence and billing. No edits
    to objects in place; output must be claimed as a distinct creative.
    """
    if operation not in ("rotate_90", "rotate_180", "flip_horizontal"):
        raise AssetImageError()
    verify_normalized_png(data)
    if sys.platform != "linux":
        raise AssetImageError("IMAGE_PROCESSING_UNAVAILABLE")
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", str(_WORKER), operation],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            close_fds=True, start_new_session=True, env={"LC_ALL": "C.UTF-8"},
        )
        output = _bounded_exchange(process, data)
    except AssetImageError:
        raise
    except Exception:
        raise AssetImageError("IMAGE_PROCESSING_UNAVAILABLE") from None
    return verify_normalized_png(output)
