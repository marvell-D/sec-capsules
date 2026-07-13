from __future__ import annotations

import unittest
from pathlib import Path

from sec_capsules.core.arguments import validate_input_schema
from sec_capsules.core.parsers import parse_capsule_output
from sec_capsules.core.planner import build_command_plan
from sec_capsules.core.registry import CapsuleRegistry


class CapsuleConformanceTest(unittest.TestCase):
    def test_every_builtin_capsule_has_valid_argument_contract_and_default_plan(self) -> None:
        registry = CapsuleRegistry()
        for capsule in registry.list():
            with self.subTest(capsule=capsule.id):
                for field in ("id", "name", "category", "summary", "stage", "risk_level"):
                    self.assertIn(field, capsule.raw)
                validate_input_schema(capsule)
                for profile in capsule.raw.get("profiles", {}):
                    plan = build_command_plan(
                        capsule,
                        target="https://example.com",
                        profile_name=str(profile),
                    )
                    self.assertTrue(plan.command)
                    self.assertNotIn("$", " ".join(plan.command))

                runtime = capsule.raw.get("runtime", {})
                self.assertIsInstance(runtime.get("binary"), str)
                self.assertTrue(runtime.get("version_command"))
                artifact_name = str(capsule.raw.get("artifacts", {}).get("primary", ""))
                self.assertTrue(artifact_name)
                fixture = capsule.root / "fixtures" / f"sample{Path(artifact_name).suffix}"
                self.assertTrue(fixture.is_file(), fixture)
                structured = parse_capsule_output(
                    capsule,
                    fixture.read_text(encoding="utf-8"),
                    run_id="run_conformance",
                    artifact_name=artifact_name,
                )
                self.assertTrue(
                    {"assets", "services", "endpoints", "findings", "evidence"}
                    <= set(structured)
                )
                for collection in ("assets", "services", "endpoints", "findings", "evidence"):
                    self.assertIsInstance(structured.get(collection, []), list)


if __name__ == "__main__":
    unittest.main()
