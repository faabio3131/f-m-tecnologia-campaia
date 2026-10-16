from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import zlib

from PIL import Image, PngImagePlugin

from campaia_core.asset_images import (
    AssetImageError, MAX_DIMENSION, MAX_PIXELS, _bounded_exchange,
    normalize_asset_image, verify_normalized_png,
)
from campaia_core.asset_storage import MAX_ASSET_BYTES, PNG_SIGNATURE


def encoded(format="PNG", *, mode="RGB", size=(3, 2), **options):
    output = io.BytesIO()
    Image.new(mode, size, (20, 40, 60, 90) if mode == "RGBA" else (20, 40, 60)).save(
        output, format=format, **options)
    return output.getvalue()


def chunk(kind, body):
    return len(body).to_bytes(4, "big") + kind + body + (zlib.crc32(kind + body) & 0xFFFFFFFF).to_bytes(4, "big")


class AssetImageTests(unittest.TestCase):
    def test_normalizes_allowed_static_formats_to_png(self):
        for format in ("PNG", "JPEG", "WEBP"):
            with self.subTest(format=format):
                normalized = normalize_asset_image(encoded(format))
                self.assertEqual((normalized.width, normalized.height), (3, 2))
                self.assertTrue(normalized.data.startswith(PNG_SIGNATURE))
                self.assertEqual(verify_normalized_png(normalized.data), normalized)
                with Image.open(io.BytesIO(normalized.data)) as result:
                    result.load()
                    self.assertEqual(result.mode, "RGB")
                    self.assertEqual(result.info, {})

    def test_png_transparency_preserved_without_metadata(self):
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Comment", "private comment")
        metadata.add_itxt("XML:com.adobe.xmp", "<private>hidden</private>")
        raw = encoded(mode="RGBA", pnginfo=metadata, icc_profile=b"private icc")
        normalized = normalize_asset_image(raw)
        with Image.open(io.BytesIO(normalized.data)) as result:
            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.getpixel((0, 0)), (20, 40, 60, 90))
            self.assertEqual(result.info, {})
        self.assertNotIn(b"private", normalized.data)
        self.assertNotIn(b"tEXt", normalized.data)
        self.assertNotIn(b"iCCP", normalized.data)

    def test_exif_orientation_applied_without_copying_exif(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[315] = "private author"
        raw = encoded("JPEG", exif=exif)
        normalized = normalize_asset_image(raw)
        self.assertEqual((normalized.width, normalized.height), (2, 3))
        with Image.open(io.BytesIO(normalized.data)) as result:
            self.assertEqual(dict(result.getexif()), {})
            self.assertEqual(result.info, {})

    def test_palette_png_transparency_becomes_rgba(self):
        source = Image.new("P", (2, 2), color=0)
        output = io.BytesIO()
        source.save(output, format="PNG", transparency=0)
        normalized = normalize_asset_image(output.getvalue())
        with Image.open(io.BytesIO(normalized.data)) as result:
            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.getpixel((0, 0))[3], 0)

    def test_rejects_non_image_unsupported_truncated_and_animated(self):
        first = Image.new("RGB", (2, 2), "red")
        second = Image.new("RGB", (2, 2), "blue")
        animated = io.BytesIO()
        first.save(animated, format="PNG", save_all=True, append_images=[second], duration=100, loop=0)
        bad = (b"<svg onload='alert(1)'/>", b"%!PS-Adobe", b"not an image",
               encoded("GIF"), encoded("BMP"), encoded("PNG")[:24], encoded("JPEG")[:40],
               animated.getvalue())
        for raw in bad:
            with self.subTest(prefix=raw[:8]), self.assertRaises(AssetImageError):
                normalize_asset_image(raw)

    def test_pixel_and_dimension_bounds_before_large_allocation(self):
        for size in ((MAX_DIMENSION + 1, 1), (2049, 2048)):
            with self.subTest(size=size), self.assertRaises(AssetImageError):
                normalize_asset_image(encoded(size=size))
        normalized = normalize_asset_image(encoded(size=(2048, 2048)))
        self.assertEqual(normalized.width * normalized.height, MAX_PIXELS)

    def test_bytes_input_bounds_fail_before_process_creation(self):
        with patch("campaia_core.asset_images.subprocess.Popen", side_effect=AssertionError("no child")) as popen:
            for raw in ("png", b"", b"x" * (MAX_ASSET_BYTES + 1), None):
                with self.assertRaises(AssetImageError):
                    normalize_asset_image(raw)
            popen.assert_not_called()

    def test_child_is_isolated_and_receives_no_application_environment(self):
        real_popen = subprocess.Popen
        seen = []
        def capture(*args, **kwargs):
            seen.append((args, kwargs))
            return real_popen(*args, **kwargs)
        with patch.dict(os.environ, {"CAMPAIA_TEST_PRIVATE_VALUE": "must-not-inherit"}):
            with patch("campaia_core.asset_images.subprocess.Popen", side_effect=capture):
                normalize_asset_image(encoded())
        args, options = seen[0]
        command = args[0]
        self.assertEqual(command[:3], [sys.executable, "-I", "-B"])
        self.assertTrue(Path(command[3]).is_absolute())
        self.assertEqual(options["env"], {"LC_ALL": "C.UTF-8"})
        self.assertTrue(options["close_fds"])
        self.assertTrue(options["start_new_session"])
        self.assertEqual(options["stderr"], subprocess.DEVNULL)
        self.assertNotIn("shell", options)

    def test_parent_checks_crc_chunks_and_no_trailing_data(self):
        raw = encoded()
        # Fresh RGB Pillow output passes; ancillary chunks from a compromised worker do not.
        verify_normalized_png(raw)
        mutations = [
            b"not-png", raw + b"trailing", raw[:-1],
            raw[:16] + bytes([raw[16] ^ 1]) + raw[17:],
            raw[:33] + chunk(b"tEXt", b"secret") + raw[33:],
            PNG_SIGNATURE + chunk(b"IDAT", b"x") + chunk(b"IEND", b""),
            PNG_SIGNATURE + chunk(b"IHDR", b"x") + chunk(b"IEND", b""),
        ]
        for invalid in mutations:
            with self.assertRaises(AssetImageError):
                verify_normalized_png(invalid)

    def test_parent_rejects_invalid_geometry_and_unsupported_png_modes(self):
        def envelope(width, height, depth=8, color=2, suffix=b"\x00\x00\x00"):
            header = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([depth, color]) + suffix
            return PNG_SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", b"x") + chunk(b"IEND", b"")
        for raw in (envelope(0, 1), envelope(MAX_DIMENSION + 1, 1), envelope(2049, 2048),
                    envelope(2, 2, depth=16), envelope(2, 2, color=3),
                    envelope(2, 2, suffix=b"\x00\x00\x01")):
            with self.assertRaises(AssetImageError):
                verify_normalized_png(raw)

    def test_parent_kills_child_on_wall_timeout(self):
        process = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(10)"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env={})
        with self.assertRaises(AssetImageError) as caught:
            _bounded_exchange(process, b"input", timeout=0.1)
        self.assertEqual(caught.exception.code, "IMAGE_PROCESSING_UNAVAILABLE")
        self.assertIsNotNone(process.poll())

    def test_parent_bounds_output_even_if_worker_misbehaves(self):
        program = "import os; " + "\nwhile True: os.write(1, b'x' * 16384)"
        process = subprocess.Popen([sys.executable, "-I", "-c", program],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env={})
        with self.assertRaises(AssetImageError):
            _bounded_exchange(process, b"input", max_output=32768, timeout=3)
        self.assertIsNotNone(process.poll())

    def test_syscall_filter_denies_files_network_and_process_creation(self):
        worker = Path(__file__).resolve().parents[1] / "campaia_core" / "asset_image_worker.py"
        program = (
            "import runpy, socket, os, sys\n"
            "worker = runpy.run_path(sys.argv[1])\n"
            "worker['install_syscall_filter']()\n"
            "checks = [lambda: open('/etc/passwd', 'rb'), lambda: socket.socket(), os.fork]\n"
            "for check in checks:\n"
            " try: check()\n"
            " except PermissionError: continue\n"
            " os._exit(10)\n"
            "os._exit(0)\n"
        )
        result = subprocess.run([sys.executable, "-I", "-B", "-c", program, str(worker)],
            env={}, close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode()[:500])

    def test_unsupported_platform_fails_closed(self):
        with patch("campaia_core.asset_images.sys.platform", "unsupported"):
            with self.assertRaises(AssetImageError) as caught:
                normalize_asset_image(encoded())
            self.assertEqual(caught.exception.code, "IMAGE_PROCESSING_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
