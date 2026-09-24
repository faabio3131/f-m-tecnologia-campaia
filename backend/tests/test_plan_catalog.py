from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from campaia_core.plan_catalog import (
    CATALOG_PATH_ENV_VAR,
    PlanCatalogError,
    get_plan,
    load_plan_catalog,
)


class PlanCatalogTests(unittest.TestCase):
    def write_catalog(self, entries: list[dict]) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(entries, tmp)
        tmp.close()
        return Path(tmp.name)

    def valid_entry(self, **overrides) -> dict:
        base = {
            "plan_id": "essencial",
            "name": "Essencial",
            "monthly_price": 199.90,
            "included_credits": 100,
            "extra_credit_unit_price": 1.50,
        }
        base.update(overrides)
        return base

    def test_loads_valid_catalog_from_explicit_path(self) -> None:
        path = self.write_catalog([self.valid_entry()])
        catalog = load_plan_catalog(path)
        self.assertIn("essencial", catalog)
        plan = catalog["essencial"]
        self.assertEqual(plan.monthly_price, Decimal("199.90"))
        self.assertEqual(plan.currency, "BRL")

    def test_loads_valid_catalog_from_environment_variable(self) -> None:
        path = self.write_catalog([self.valid_entry()])
        import os

        old = os.environ.get(CATALOG_PATH_ENV_VAR)
        os.environ[CATALOG_PATH_ENV_VAR] = str(path)
        try:
            catalog = load_plan_catalog()
            self.assertIn("essencial", catalog)
        finally:
            if old is None:
                os.environ.pop(CATALOG_PATH_ENV_VAR, None)
            else:
                os.environ[CATALOG_PATH_ENV_VAR] = old

    def test_missing_file_fails_closed(self) -> None:
        with self.assertRaises(PlanCatalogError):
            load_plan_catalog("/nao/existe/plans.json")

    def test_no_path_configured_fails_closed(self) -> None:
        import os

        old = os.environ.pop(CATALOG_PATH_ENV_VAR, None)
        try:
            with self.assertRaises(PlanCatalogError):
                load_plan_catalog()
        finally:
            if old is not None:
                os.environ[CATALOG_PATH_ENV_VAR] = old

    def test_malformed_json_fails_closed(self) -> None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        tmp.write("{ nao é json valido")
        tmp.close()
        with self.assertRaises(PlanCatalogError):
            load_plan_catalog(tmp.name)

    def test_not_a_list_fails_closed(self) -> None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"plan_id": "x"}, tmp)
        tmp.close()
        with self.assertRaises(PlanCatalogError):
            load_plan_catalog(tmp.name)

    def test_missing_required_field_fails_closed(self) -> None:
        entry = self.valid_entry()
        del entry["monthly_price"]
        path = self.write_catalog([entry])
        with self.assertRaises(PlanCatalogError):
            load_plan_catalog(path)

    def test_invalid_value_fails_closed(self) -> None:
        path = self.write_catalog([self.valid_entry(monthly_price=-10)])
        with self.assertRaises(PlanCatalogError):
            load_plan_catalog(path)

    def test_duplicate_plan_id_fails_closed(self) -> None:
        path = self.write_catalog([self.valid_entry(), self.valid_entry(name="Outro nome")])
        with self.assertRaises(PlanCatalogError):
            load_plan_catalog(path)

    def test_empty_catalog_fails_closed(self) -> None:
        path = self.write_catalog([])
        with self.assertRaises(PlanCatalogError):
            load_plan_catalog(path)

    def test_get_plan_returns_the_right_plan(self) -> None:
        path = self.write_catalog(
            [self.valid_entry(), self.valid_entry(plan_id="pro", name="Pro", monthly_price=499.90)]
        )
        catalog = load_plan_catalog(path)
        self.assertEqual(get_plan("pro", catalog).monthly_price, Decimal("499.90"))

    def test_get_plan_unknown_id_fails_closed(self) -> None:
        path = self.write_catalog([self.valid_entry()])
        catalog = load_plan_catalog(path)
        with self.assertRaises(PlanCatalogError):
            get_plan("nao-existe", catalog)

    def test_example_template_file_is_itself_loadable(self) -> None:
        """O template versionado no repositorio (config/plans.example.json) precisa ser um
        JSON valido e carregavel de verdade — nao so um texto solto que parece JSON."""
        example_path = (
            Path(__file__).resolve().parent.parent / "config" / "plans.example.json"
        )
        catalog = load_plan_catalog(example_path)
        self.assertGreaterEqual(len(catalog), 1)


if __name__ == "__main__":
    unittest.main()
