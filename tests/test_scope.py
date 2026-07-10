from __future__ import annotations

import unittest

from sec_capsules.core.scope import ScopePolicy


class ScopeTest(unittest.TestCase):
    def test_allows_in_scope_localhost_when_private_allowed(self) -> None:
        policy = ScopePolicy(
            {
                "scope": {
                    "include": ["http://localhost:3000", "localhost:3000"],
                    "allow_private_ip": True,
                    "allow_active_scan": True,
                }
            }
        )
        decision = policy.decide("http://localhost:3000", active=True)
        self.assertTrue(decision.allowed, decision.reasons)

    def test_blocks_out_of_scope_target(self) -> None:
        policy = ScopePolicy({"scope": {"include": ["example.com"], "allow_private_ip": False}})
        decision = policy.decide("https://evil.example.net")
        self.assertFalse(decision.allowed)

    def test_blocks_metadata_ip_even_when_private_allowed(self) -> None:
        policy = ScopePolicy({"scope": {"include": ["169.254.169.254"], "allow_private_ip": True}})
        decision = policy.decide("http://169.254.169.254/latest/meta-data")
        self.assertFalse(decision.allowed)


if __name__ == "__main__":
    unittest.main()

