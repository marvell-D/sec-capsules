from __future__ import annotations

import sys
import unittest

from sec_capsules.core.executor import extract_version, run_command


class ExecutorTest(unittest.TestCase):
    def test_caps_output_and_marks_truncation(self) -> None:
        result = run_command(
            [sys.executable, "-c", "import sys; print('x' * 1000); print('e' * 1000, file=sys.stderr)"],
            timeout=5,
            max_output_bytes=100,
        )
        self.assertEqual(0, result.exit_code)
        self.assertTrue(result.output_truncated)
        self.assertLessEqual(len(result.stdout.encode("utf-8")), 100)
        self.assertLessEqual(len(result.stderr.encode("utf-8")), 100)

    def test_timeout_returns_a_terminal_result(self) -> None:
        result = run_command(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=1,
        )
        self.assertTrue(result.timed_out)
        self.assertIsNotNone(result.exit_code)

    def test_extracts_version_after_a_banner(self) -> None:
        version = extract_version(["  __ banner __", "\x1b[34m[INF]\x1b[0m Current Version: v1.2.3"])
        self.assertEqual("[INF] Current Version: v1.2.3", version)


if __name__ == "__main__":
    unittest.main()
