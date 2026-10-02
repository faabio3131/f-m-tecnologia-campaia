"""Prova arquitetural: `tests_support` (harness de E2E, item 1.3/Etapa 2 Web) nunca e
importado por codigo de producao (`api/`, `campaia_core/`). Varredura estatica de texto
-- mesma disciplina do `boundary:check` do frontend
(`web/scripts/check-security-boundaries.mjs`)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_PRODUCTION_DIRS = ("api", "campaia_core")
_FORBIDDEN_IMPORT = re.compile(r"^\s*(from|import)\s+tests_support\b", re.MULTILINE)


class TestsSupportNeverImportedByProduction(unittest.TestCase):
    def test_no_production_file_imports_tests_support(self) -> None:
        offenders: list[str] = []
        for prod_dir in _PRODUCTION_DIRS:
            for path in (_BACKEND_ROOT / prod_dir).rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if _FORBIDDEN_IMPORT.search(text):
                    offenders.append(str(path.relative_to(_BACKEND_ROOT)))
        self.assertEqual(
            offenders,
            [],
            f"Codigo de producao nunca pode importar tests_support (harness de E2E "
            f"exclusivo de teste). Ofensores: {offenders}",
        )

    def test_tests_support_directory_exists_and_is_not_empty(self) -> None:
        """Guarda contra o teste acima passar trivialmente por o diretorio nao
        existir/estar vazio (falso positivo de 'nenhum ofensor')."""
        tests_support_dir = _BACKEND_ROOT / "tests_support"
        self.assertTrue(tests_support_dir.is_dir())
        py_files = list(tests_support_dir.glob("*.py"))
        self.assertGreater(len(py_files), 1)


if __name__ == "__main__":
    unittest.main()
