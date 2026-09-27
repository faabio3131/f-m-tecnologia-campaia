#!/usr/bin/env python3
"""Verificação estática rápida para arquivos .dart, sem depender do SDK Flutter.

Criado para substituir a checagem manual (ler o arquivo e contar chaves na
cabeça) por um resultado determinístico e repetível. NÃO substitui
`flutter analyze`/`flutter test` — é uma rede de segurança rápida para
pegar os erros mais óbvios (chaves/parênteses desbalanceados, import
relativo que não resolve para um arquivo existente) antes de qualquer commit.

Uso:
    python3 scripts/verify_dart.py            # verifica lib/ e test/
    python3 scripts/verify_dart.py caminho/   # verifica só esse caminho
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BRACE_PAIRS = {"{": "}", "(": ")", "[": "]"}
CLOSERS = {v: k for k, v in BRACE_PAIRS.items()}

IMPORT_RE = re.compile(r"""^\s*import\s+['"](\.\.?/[^'"]+)['"]""", re.MULTILINE)


def strip_comments_and_strings(text: str) -> str:
    """Remove line comments, block comments and string literals so brace
    counting doesn't get confused by '{' inside a string or comment."""
    # Block comments
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # Line comments
    text = re.sub(r"//[^\n]*", "", text)
    # Triple-ish / normal string literals (single and double quoted,
    # including simple escaped-quote handling). Not a full Dart lexer, but
    # good enough for balance-checking purposes.
    text = re.sub(r"'(?:\\.|[^'\\])*'", "''", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    return text


def check_balance(path: Path) -> list[str]:
    errors: list[str] = []
    raw = path.read_text(encoding="utf-8")
    text = strip_comments_and_strings(raw)
    stack: list[tuple[str, int]] = []
    line = 1
    for ch in text:
        if ch == "\n":
            line += 1
            continue
        if ch in BRACE_PAIRS:
            stack.append((ch, line))
        elif ch in CLOSERS:
            if not stack or stack[-1][0] != CLOSERS[ch]:
                errors.append(
                    f"{path}:{line}: '{ch}' sem abertura correspondente "
                    f"(topo da pilha: {stack[-1] if stack else 'vazia'})"
                )
            else:
                stack.pop()
    if stack:
        for ch, ln in stack:
            errors.append(f"{path}:{ln}: '{ch}' nunca foi fechado")
    return errors


def check_imports(path: Path) -> list[str]:
    errors: list[str] = []
    raw = path.read_text(encoding="utf-8")
    for match in IMPORT_RE.finditer(raw):
        rel = match.group(1)
        target = (path.parent / rel).resolve()
        if not target.exists():
            line_no = raw.count("\n", 0, match.start()) + 1
            errors.append(
                f"{path}:{line_no}: import relativo não resolve: '{rel}' "
                f"(esperado em {target})"
            )
    return errors


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent
    targets = [Path(a) for a in argv] if argv else [root / "lib", root / "test"]

    dart_files: list[Path] = []
    for t in targets:
        if t.is_file() and t.suffix == ".dart":
            dart_files.append(t)
        elif t.is_dir():
            dart_files.extend(sorted(t.rglob("*.dart")))

    if not dart_files:
        print("Nenhum arquivo .dart encontrado nos caminhos informados.")
        return 1

    all_errors: list[str] = []
    for f in dart_files:
        all_errors.extend(check_balance(f))
        all_errors.extend(check_imports(f))

    print(f"Verificados {len(dart_files)} arquivo(s) .dart.")
    if all_errors:
        print(f"\n{len(all_errors)} problema(s) encontrado(s):\n")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print("Nenhum problema de balanceamento ou import encontrado.")
    print(
        "Lembrete: isto NÃO substitui 'flutter analyze'/'flutter test' — "
        "é só uma checagem rápida de sintaxe/estrutura."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
