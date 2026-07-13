from __future__ import annotations

import unittest
from importlib.metadata import PackageNotFoundError, version

from sec_capsules import __version__


class VersionTest(unittest.TestCase):
    def test_runtime_version_matches_project_metadata(self) -> None:
        try:
            package_version = version("sec-capsules")
        except PackageNotFoundError:
            self.skipTest("project metadata is unavailable without an installed package")
        self.assertEqual(package_version, __version__)


if __name__ == "__main__":
    unittest.main()
