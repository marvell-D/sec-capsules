from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sec_capsules.core.recipe import order_steps, run_recipe


class RecipeTest(unittest.TestCase):
    def test_orders_static_dependencies_and_hides_structured_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scope = root / "scope.yml"
            scope.write_text(
                "\n".join(
                    [
                        "scope:",
                        '  include: ["http://localhost:3000"]',
                        "  allow_private_ip: true",
                        "  allow_active_scan: true",
                    ]
                ),
                encoding="utf-8",
            )
            recipe = root / "recipe.yml"
            recipe.write_text(
                "\n".join(
                    [
                        "id: dependency-test",
                        "steps:",
                        "  - id: scan",
                        "    capsule: nuclei",
                        "    depends_on: [probe]",
                        "  - id: probe",
                        "    capsule: httpx",
                    ]
                ),
                encoding="utf-8",
            )
            source_root = Path(__file__).resolve().parents[1] / "src" / "sec_capsules" / "capsules"
            result = run_recipe(
                str(recipe),
                target="http://localhost:3000",
                scope_file=scope,
                fixtures={
                    "httpx": str(source_root / "httpx" / "fixtures" / "sample.jsonl"),
                    "nuclei": str(source_root / "nuclei" / "fixtures" / "sample.jsonl"),
                },
                arguments_by_step={
                    "probe": {"requests_per_second": 3},
                    "scan": {"severity": ["critical"], "requests_per_second": 2},
                },
                runs_dir=root / "runs",
            )
            self.assertEqual(["probe", "scan"], [step["step_id"] for step in result["steps"]])
            self.assertNotIn("structured", result["steps"][0])
            self.assertEqual(3, result["steps"][0]["arguments"]["requests_per_second"])
            self.assertEqual(["critical"], result["steps"][1]["arguments"]["severity"])
            self.assertTrue(result["observation"]["hidden_from_model"]["raw_artifacts"])

    def test_rejects_cyclic_dependencies(self) -> None:
        with self.assertRaisesRegex(ValueError, "cycle"):
            order_steps(
                [
                    {"id": "a", "capsule": "httpx", "depends_on": ["b"]},
                    {"id": "b", "capsule": "katana", "depends_on": ["a"]},
                ]
            )

    def test_rejects_arguments_for_unknown_recipe_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = root / "recipe.yml"
            recipe.write_text(
                "id: one-step\nsteps:\n  - id: probe\n    capsule: httpx\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown recipe steps"):
                run_recipe(
                    str(recipe),
                    target="https://example.com",
                    scope_file=root / "unused-scope.yml",
                    arguments_by_step={"typo": {"requests_per_second": 1}},
                    runs_dir=root / "runs",
                )


if __name__ == "__main__":
    unittest.main()
