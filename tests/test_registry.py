from __future__ import annotations

import unittest

from sec_capsules.core.registry import CapsuleRegistry, capsule_to_public_dict


class RegistryTest(unittest.TestCase):
    def test_loads_builtin_capsules(self) -> None:
        registry = CapsuleRegistry()
        capsule_ids = {capsule.id for capsule in registry.list()}
        self.assertEqual({"ffuf", "httpx", "katana", "nmap", "nuclei"}, capsule_ids)

    def test_usage_view_hides_full_command_details(self) -> None:
        registry = CapsuleRegistry()
        usage = capsule_to_public_dict(registry.get("nuclei"), "usage")
        self.assertEqual("nuclei", usage["id"])
        self.assertIn("best_for", usage)
        self.assertIn("profiles", usage)
        self.assertIn("input_schema", usage)
        self.assertIn("severity", usage["input_schema"]["properties"])
        self.assertNotIn("command", str(usage))


if __name__ == "__main__":
    unittest.main()
