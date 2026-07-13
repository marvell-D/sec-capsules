from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sec_capsules.core.runner import CapsuleRunner


class RunnerTest(unittest.TestCase):
    def test_fixture_run_writes_artifacts_and_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scope = tmp_path / "scope.yml"
            scope.write_text(
                """
scope:
  include:
    - "http://localhost:3000"
    - "localhost:3000"
  allow_private_ip: true
  allow_active_scan: true
""".strip(),
                encoding="utf-8",
            )
            fixture = (
                Path(__file__).resolve().parents[1]
                / "src"
                / "sec_capsules"
                / "capsules"
                / "nuclei"
                / "fixtures"
                / "sample.jsonl"
            )
            runner = CapsuleRunner(runs_dir=tmp_path / "runs")
            result = runner.run(
                "nuclei",
                target="http://localhost:3000",
                scope_file=scope,
                arguments={"severity": ["critical"], "requests_per_second": 2},
                fixture=fixture,
            )

            self.assertFalse(result.dry_run)
            self.assertEqual(2, len(result.structured["findings"]))
            self.assertEqual("observation_packet.v1", result.observation["type"])
            self.assertEqual(["critical"], result.arguments["severity"])
            self.assertEqual("agent", result.argument_sources["severity"])
            self.assertTrue((tmp_path / "runs" / result.run_id / "run.json").exists())

    def test_plan_builds_expected_command(self) -> None:
        runner = CapsuleRunner()
        plan = runner.plan("nuclei", target="http://localhost:3000")
        self.assertEqual("nuclei", plan["command"][0])
        self.assertIn("-severity", plan["command"])
        self.assertIn("medium,high,critical", plan["command"])

    def test_plan_accepts_semantic_arguments_without_raw_argv(self) -> None:
        plan = CapsuleRunner().plan(
            "katana",
            target="https://example.com",
            arguments={"depth": 1, "requests_per_second": 3},
        )
        self.assertEqual({"depth": 1, "requests_per_second": 3}, plan["arguments"])
        self.assertEqual("agent", plan["argument_sources"]["depth"])
        self.assertNotIn("extra_args", plan)

    def test_missing_tool_is_recorded_as_preflight_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scope = tmp_path / "scope.yml"
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
            capsules = tmp_path / "capsules" / "missing"
            capsules.mkdir(parents=True)
            (capsules / "capsule.yml").write_text(
                "\n".join(
                    [
                        "id: missing",
                        "name: missing",
                        "category: test",
                        "summary: test capsule",
                        "profiles:",
                        "  safe:",
                        "    active: true",
                        "    action: test",
                        '    command: ["definitely-not-an-installed-tool"]',
                        "runtime:",
                        "  binary: definitely-not-an-installed-tool",
                        "outputs: {}",
                        "artifacts: {}",
                    ]
                ),
                encoding="utf-8",
            )
            from sec_capsules.core.registry import CapsuleRegistry

            runner = CapsuleRunner(
                registry=CapsuleRegistry(root=tmp_path / "capsules"),
                runs_dir=tmp_path / "runs",
            )
            result = runner.run(
                "missing",
                target="http://localhost:3000",
                scope_file=scope,
                execute=True,
            )
            self.assertEqual("preflight_failed", result.status)
            self.assertFalse(result.tool["available"])

    def test_nmap_fixture_run_requires_approval_and_audits_packet_rate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scope = root / "scope.yml"
            scope.write_text(
                "\n".join(
                    [
                        "scope:",
                        '  include: ["127.0.0.1"]',
                        "  allow_private_ip: true",
                        "  allow_active_scan: true",
                        "  max_rates:",
                        "    packets_per_second: 40",
                    ]
                ),
                encoding="utf-8",
            )
            approval = root / "approval.yml"
            approval.write_text(
                "\n".join(
                    [
                        "approval:",
                        "  id: apr_nmap_test",
                        "  approved_by: test-operator",
                        "  actions: [port_scan]",
                        '  targets: ["127.0.0.1"]',
                    ]
                ),
                encoding="utf-8",
            )
            fixture = (
                Path(__file__).resolve().parents[1]
                / "src"
                / "sec_capsules"
                / "capsules"
                / "nmap"
                / "fixtures"
                / "sample.xml"
            )
            runner = CapsuleRunner(runs_dir=root / "runs")
            with self.assertRaisesRegex(PermissionError, "approval"):
                runner.run("nmap", target="127.0.0.1", scope_file=scope, fixture=fixture)
            result = runner.run(
                "nmap",
                target="127.0.0.1",
                scope_file=scope,
                arguments={"packets_per_second": 25},
                approval_file=approval,
                fixture=fixture,
            )
            self.assertEqual("replayed", result.status)
            self.assertEqual(4, len(result.structured["services"]))
            self.assertEqual("packets_per_second", result.rate_limit["unit"])
            self.assertTrue(result.scope_decision["rate_limit"]["allowed"])
            self.assertIn("1 asset(s)", result.observation["summary"])


if __name__ == "__main__":
    unittest.main()
