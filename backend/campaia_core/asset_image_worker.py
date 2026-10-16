"""Restricted image decoder entrypoint. Only the parent normalizer may invoke it.

This module never runs image parsing at import. It preloads a three-format allowlist,
sets resource limits and installs a Linux syscall filter BEFORE reading untrusted input.
The filter is one isolation layer, not a claim of a complete security sandbox / F16.
"""
from __future__ import annotations

import ctypes
import io
import os
import platform
import resource
import sys
import warnings

_MAX_BYTES = 5 * 1024 * 1024
_MAX_PIXELS = 4_194_304
_MAX_DIMENSION = 8192


def install_syscall_filter():
    """Linux UAPI constants checked against torvalds/linux, 2026-10-16.

    No open/openat, sockets, exec, fork/clone, ptrace, filesystem mutations or io_uring.
    The process has only stdin/stdout/stderr and no inherited application credentials.
    Unsupported architectures/kernels fail closed; never fall back to an unfiltered decoder.
    """
    if sys.platform != "linux":
        raise RuntimeError("unsupported isolation")
    architecture = platform.machine()
    if architecture == "x86_64":
        audit_arch = 0xC000003E
        numbers = (0, 1, 3, 5, 8, 9, 10, 11, 12, 13, 14, 15, 24, 39, 60,
                   72, 131, 186, 202, 219, 228, 231, 318)
    elif architecture == "aarch64":
        audit_arch = 0xC00000B7
        numbers = (25, 57, 62, 63, 64, 80, 93, 94, 98, 113, 124, 128, 132,
                   134, 135, 139, 172, 178, 214, 215, 222, 226, 278)
    else:
        raise RuntimeError("unsupported isolation")

    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                    ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]

    class Program(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ushort), ("filters", ctypes.POINTER(Filter))]

    # LD arch; expected ABI skips KILL, all others terminate. Then load syscall number.
    instructions = [(0x20, 0, 0, 4), (0x15, 1, 0, audit_arch),
                    (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0)]
    for number in numbers:
        instructions.extend([(0x15, 0, 1, number), (0x06, 0, 0, 0x7FFF0000)])
    instructions.append((0x06, 0, 0, 0x00050001))  # ERRNO | EPERM
    filters = (Filter * len(instructions))(*(Filter(*item) for item in instructions))
    program = Program(len(instructions), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(38, 1, None, 0, 0) != 0:
        raise RuntimeError("isolation unavailable")
    if libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
        raise RuntimeError("isolation unavailable")


def _limits():
    resource.setrlimit(resource.RLIMIT_AS, (160 * 1024 * 1024, 160 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (4, 5))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    resource.setrlimit(resource.RLIMIT_FSIZE, (_MAX_BYTES, _MAX_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    try:
        _limits()
        # Preload all needed modules/libraries before forbidding filesystem access.
        from PIL import Image, ImageFile, ImageOps, PngImagePlugin, JpegImagePlugin, WebPImagePlugin, TiffImagePlugin
        # Explicit references document the bounded plugin allowlist / EXIF support.
        _ = PngImagePlugin, JpegImagePlugin, WebPImagePlugin, TiffImagePlugin
        Image.preinit()  # Image.open invokes this even with a formats allowlist.
        Image.MAX_IMAGE_PIXELS = _MAX_PIXELS
        ImageFile.LOAD_TRUNCATED_IMAGES = False
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        install_syscall_filter()
    except Exception:
        os._exit(3)

    try:
        data = sys.stdin.buffer.read(_MAX_BYTES + 1)
        if not data or len(data) > _MAX_BYTES:
            raise ValueError("invalid image")
        allowed = ("PNG", "JPEG", "WEBP")
        with Image.open(io.BytesIO(data), formats=allowed) as check:
            width, height = check.size
            if (min(width, height) < 1 or max(width, height) > _MAX_DIMENSION
                    or width * height > _MAX_PIXELS or getattr(check, "n_frames", 1) != 1):
                raise ValueError("invalid image")
            check.verify()
        with Image.open(io.BytesIO(data), formats=allowed) as image:
            image.load()
            ImageOps.exif_transpose(image, in_place=True)
            mode = "RGBA" if image.mode in ("RGBA", "LA") or "transparency" in image.info else "RGB"
            pixels = image.convert(mode)
            # A fresh image prevents propagation of comments, EXIF, ICC, XMP or extra chunks.
            clean = Image.new(mode, pixels.size)
            clean.paste(pixels)
            output = io.BytesIO()
            clean.save(output, format="PNG", optimize=False)
            normalized = output.getvalue()
            if len(normalized) > _MAX_BYTES:
                raise ValueError("invalid image")
            sys.stdout.buffer.write(normalized)
            sys.stdout.buffer.flush()
        os._exit(0)
    except Exception:
        os._exit(2)


if __name__ == "__main__":
    main()
