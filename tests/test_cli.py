from __future__ import annotations

import unittest

from sec_capsules.interfaces.cli import build_parser, parse_json_object, parse_nested_json_object


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

    def test_semantic_argument_json_is_parsed_as_structured_data(self) -> None:
        self.assertEqual(
            {"depth": 1},
            parse_json_object('{"depth": 1}', "--arguments-json"),
        )
        self.assertEqual(
            {"crawl": {"depth": 1}},
            parse_nested_json_object(
                '{"crawl": {"depth": 1}}',
                "--arguments-by-step-json",
            ),
        )
        with self.assertRaisesRegex(ValueError, "JSON object"):
            parse_json_object("[]", "--arguments-json")


if __name__ == "__main__":
    unittest.main()
