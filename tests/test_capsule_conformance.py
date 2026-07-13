from __future__ import annotations

import unittest

from sec_capsules.core.arguments import validate_input_schema
from sec_capsules.core.planner import build_command_plan
from sec_capsules.core.registry import CapsuleRegistry


class CapsuleConformanceTest(unittest.TestCase):
    def test_every_builtin_capsule_has_valid_argument_contract_and_default_plan(self) -> None:
        registry = CapsuleRegistry()
        for capsule in registry.list():
            with self.subTest(capsule=capsule.id):
                validate_input_schema(capsule)
                for profile in capsule.raw.get("profiles", {}):
                    plan = build_command_plan(
                        capsule,
                        target="https://example.com",
                        profile_name=str(profile),
                    )
                    self.assertTrue(plan.command)
                    self.assertNotIn("$", " ".join(plan.command))


if __name__ == "__main__":
    unittest.main()
