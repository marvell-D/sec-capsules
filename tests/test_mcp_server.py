from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sec_capsules.core.runner import CapsuleRunner
from sec_capsules.interfaces import mcp_server


class McpServerTest(unittest.TestCase):
    def test_observation_artifact_and_export_are_rooted_in_runs_dir(self) -> None:
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
            fixture = (
                Path(__file__).resolve().parents[1]
                / "src"
                / "sec_capsules"
                / "capsules"
                / "nuclei"
                / "fixtures"
                / "sample.jsonl"
            )
            result = CapsuleRunner(runs_dir=root / "runs").run(
                "nuclei",
                target="http://localhost:3000",
                scope_file=scope,
                fixture=fixture,
            )
            with patch.dict(os.environ, {"SEC_CAPSULES_RUNS_DIR": str(root / "runs")}, clear=False):
                observation = mcp_server.get_observation(result.run_id)
                artifact = mcp_server.get_artifact(result.structured["findings"][0]["evidence_refs"][0])
                exported = mcp_server.export_run(result.run_id)

            self.assertEqual(result.run_id, observation["run_id"])
            self.assertIn("template-id", artifact["content"])
            self.assertIn("# sec-capsules run", exported["content"])

    def test_mcp_rejects_live_execution_until_host_enables_it(self) -> None:
        with patch.dict(os.environ, {"SEC_CAPSULES_ALLOW_MCP_EXECUTE": "0"}, clear=False):
            with self.assertRaises(PermissionError):
                mcp_server.run_capsule(
                    "httpx",
                    "http://localhost:3000",
                    "scope.yml",
                    execute=True,
                )


if __name__ == "__main__":
    unittest.main()
