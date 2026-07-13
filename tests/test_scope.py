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

    def test_blocks_public_name_that_resolves_to_private_address(self) -> None:
        policy = ScopePolicy(
            {"scope": {"include": ["example.com"], "allow_private_ip": False}},
            resolver=lambda host: ["10.0.0.8"],
        )
        decision = policy.decide("https://example.com", resolve_dns=True)
        self.assertFalse(decision.allowed)
        self.assertIn("10.0.0.8", " ".join(decision.reasons))

    def test_enforces_requested_requests_per_second(self) -> None:
        policy = ScopePolicy(
            {"scope": {"include": ["example.com"], "max_requests_per_second": 5}}
        )
        decision = policy.decide("https://example.com", requested_requests_per_second=10)
        self.assertFalse(decision.allowed)

    def test_converts_legacy_per_minute_limit_without_overstating_capacity(self) -> None:
        policy = ScopePolicy(
            {"scope": {"include": ["example.com"], "max_requests_per_minute": 60}}
        )
        allowed = policy.decide("https://example.com", requested_requests_per_second=1)
        denied = policy.decide("https://example.com", requested_requests_per_second=2)
        self.assertTrue(allowed.allowed, allowed.reasons)
        self.assertFalse(denied.allowed)

    def test_rejects_non_positive_scope_rate_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            ScopePolicy({"scope": {"max_requests_per_second": 0}})

    def test_requires_target_bound_approval_record(self) -> None:
        policy = ScopePolicy(
            {"scope": {"include": ["example.com"], "require_approval_for": ["credentialed_scan"]}}
        )
        denied = policy.decide("https://example.com", action="credentialed_scan")
        self.assertFalse(denied.allowed)

        allowed = policy.decide(
            "https://example.com",
            action="credentialed_scan",
            approval={
                "id": "apr_demo_001",
                "approved_by": "operator",
                "actions": ["credentialed_scan"],
                "targets": ["example.com"],
            },
        )
        self.assertTrue(allowed.allowed, allowed.reasons)
        self.assertTrue(allowed.approval["approved"])


if __name__ == "__main__":
    unittest.main()
