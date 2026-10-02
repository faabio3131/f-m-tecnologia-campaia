#!/usr/bin/env python3
"""High-confidence repository secret scan used by the F4 platform CI gate.

This intentionally focuses on credential formats that should never appear in Git. It does
not replace provider-side secret scanning, but it gives the repository a deterministic,
credential-free blocking gate that works on every PR.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


PATTERNS = {
    "private-key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "stripe-live-key": re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b"),
    "asaas-production-key": re.compile(
        r"\$aact_(?:prod|production)_[A-Za-z0-9_-]{20,}"
    ),
}

SKIP = {
    "infra/scripts/scan-secrets.py",
}


def tracked_files() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"])
    return [
        Path(item.decode("utf-8"))
        for item in raw.split(b"\x00")
        if item
    ]


def main() -> int:
    findings: list[tuple[str, int, str]] = []
    for path in tracked_files():
        posix = path.as_posix()
        if posix in SKIP or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((posix, line_number, name))

    if findings:
        print("High-confidence secret patterns found:")
        for path, line, name in findings:
            print(f"  {path}:{line}: {name}")
        return 1

    print("Secret scan passed: no high-confidence credential patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
