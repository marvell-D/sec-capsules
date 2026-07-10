from __future__ import annotations

import unittest

from sec_capsules.interfaces.cli import build_parser


class CliTest(unittest.TestCase):
    def test_global_runs_dir_survives_run_subcommand_defaults(self) -> None:
        args = build_parser().parse_args(
            [
                "--runs-dir",
                "custom-runs",
                "run",
                "httpx",
                "--target",
                "http://localhost:3000",
                "--scope",
                "scope.yml",
            ]
        )
        self.assertEqual("custom-runs", args.runs_dir)

    def test_run_subcommand_can_override_runs_dir(self) -> None:
        args = build_parser().parse_args(
            [
                "run",
                "httpx",
                "--target",
                "http://localhost:3000",
                "--scope",
                "scope.yml",
                "--runs-dir",
                "custom-runs",
            ]
        )
        self.assertEqual("custom-runs", args.runs_dir)


if __name__ == "__main__":
    unittest.main()
