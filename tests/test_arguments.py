from __future__ import annotations

import unittest

from sec_capsules.core.arguments import resolve_arguments
from sec_capsules.core.planner import build_command_plan
from sec_capsules.core.registry import CapsuleRegistry


class ArgumentsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CapsuleRegistry()

    def test_profile_defaults_are_resolved_and_audited(self) -> None:
        resolved = resolve_arguments(self.registry.get("katana"), "safe")
        self.assertEqual({"depth": 2, "requests_per_second": 10}, resolved.values)
        self.assertEqual("profile_default", resolved.sources["depth"])

    def test_agent_arguments_override_defaults_and_compile_to_argv(self) -> None:
        plan = build_command_plan(
            self.registry.get("katana"),
            "https://example.com",
            arguments={"depth": 1, "requests_per_second": 3},
        )
        self.assertEqual(1, plan.arguments["depth"])
        self.assertEqual("agent", plan.argument_sources["depth"])
        self.assertEqual("1", plan.command[plan.command.index("-depth") + 1])
        self.assertEqual("3", plan.command[plan.command.index("-rate-limit") + 1])

    def test_rejects_unknown_wrong_type_and_out_of_range_arguments(self) -> None:
        capsule = self.registry.get("katana")
        with self.assertRaisesRegex(ValueError, "unknown arguments"):
            resolve_arguments(capsule, "safe", {"extra_args": "--help"})
        with self.assertRaisesRegex(ValueError, "type integer"):
            resolve_arguments(capsule, "safe", {"depth": "1"})
        with self.assertRaisesRegex(ValueError, "<= 5"):
            resolve_arguments(capsule, "safe", {"depth": 100})
        with self.assertRaisesRegex(ValueError, "arguments must be an object"):
            resolve_arguments(capsule, "safe", [])  # type: ignore[arg-type]

    def test_profile_cannot_enable_arguments_it_does_not_allow(self) -> None:
        with self.assertRaisesRegex(ValueError, "not enabled"):
            resolve_arguments(
                self.registry.get("nuclei"),
                "local_lab",
                {"severity": ["critical"]},
            )

    def test_array_items_are_validated_and_serialized(self) -> None:
        capsule = self.registry.get("nuclei")
        plan = build_command_plan(
            capsule,
            "https://example.com",
            arguments={"severity": ["high", "critical"]},
        )
        self.assertIn("high,critical", plan.command)
        with self.assertRaisesRegex(ValueError, "one of"):
            resolve_arguments(capsule, "safe", {"severity": ["low"]})
        with self.assertRaisesRegex(ValueError, "unique"):
            resolve_arguments(capsule, "safe", {"severity": ["high", "high"]})

    def test_nmap_ports_compile_without_exposing_arbitrary_argv(self) -> None:
        capsule = self.registry.get("nmap")
        plan = build_command_plan(
            capsule,
            "127.0.0.1",
            arguments={"ports": [5500, 8025, 8888], "packets_per_second": 25},
        )
        self.assertEqual("5500,8025,8888", plan.command[plan.command.index("-p") + 1])
        self.assertEqual("packets_per_second", plan.rate_limit.unit)
        self.assertEqual(25, plan.rate_limit.value)
        self.assertNotIn("--script", plan.command)
        with self.assertRaisesRegex(ValueError, "<= 65535"):
            resolve_arguments(capsule, "safe", {"ports": [70000]})
        with self.assertRaisesRegex(ValueError, "unique"):
            resolve_arguments(capsule, "safe", {"ports": [80, 80]})


if __name__ == "__main__":
    unittest.main()
