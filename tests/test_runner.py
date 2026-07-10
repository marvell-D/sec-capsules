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
                fixture=fixture,
            )

            self.assertFalse(result.dry_run)
            self.assertEqual(2, len(result.structured["findings"]))
            self.assertEqual("observation_packet.v1", result.observation["type"])
            self.assertTrue((tmp_path / "runs" / result.run_id / "run.json").exists())

    def test_plan_builds_expected_command(self) -> None:
        runner = CapsuleRunner()
        plan = runner.plan("nuclei", target="http://localhost:3000")
        self.assertEqual("nuclei", plan["command"][0])
        self.assertIn("-severity", plan["command"])
        self.assertIn("medium,high,critical", plan["command"])


if __name__ == "__main__":
    unittest.main()

