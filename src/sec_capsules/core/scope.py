from __future__ import annotations

import fnmatch
import ipaddress
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml


METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
}


@dataclass
class ScopeDecision:
    allowed: bool
    reasons: list[str]

    def raise_if_denied(self) -> None:
        if not self.allowed:
            raise PermissionError("; ".join(self.reasons))


class ScopePolicy:
    def __init__(self, raw: dict) -> None:
        scope = raw.get("scope", raw)
        self.include = list(scope.get("include", []))
        self.exclude = list(scope.get("exclude", []))
        self.max_requests_per_minute = int(scope.get("max_requests_per_minute", 60))
        self.allow_private_ip = bool(scope.get("allow_private_ip", False))
        self.allow_active_scan = bool(scope.get("allow_active_scan", False))
        self.require_approval_for = set(scope.get("require_approval_for", []))

    @classmethod
    def from_file(cls, path: str | Path) -> "ScopePolicy":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(raw)

    def decide(self, target: str, action: str | None = None, active: bool = False) -> ScopeDecision:
        reasons: list[str] = []
        parsed = parse_target(target)
        host = parsed["host"]

        if not host:
            reasons.append(f"target has no host: {target}")

        if active and not self.allow_active_scan:
            reasons.append("active scan is not allowed by scope policy")

        if action and action in self.require_approval_for:
            reasons.append(f"action {action!r} requires explicit approval")

        if host and is_blocked_private_host(host, self.allow_private_ip):
            reasons.append(f"private or metadata host is not allowed: {host}")

        if self.include and not any(match_scope_pattern(target, host, pattern) for pattern in self.include):
            reasons.append(f"target is not included in scope: {target}")

        if any(match_scope_pattern(target, host, pattern) for pattern in self.exclude):
            reasons.append(f"target is excluded by scope policy: {target}")

        return ScopeDecision(allowed=not reasons, reasons=reasons)


def parse_target(target: str) -> dict[str, str]:
    value = target.strip()
    parsed = urlparse(value if "://" in value else f"//{value}", scheme="http")
    host = parsed.hostname or ""
    return {
        "scheme": parsed.scheme,
        "host": host.lower().rstrip("."),
        "netloc": parsed.netloc,
        "path": parsed.path,
    }


def is_blocked_private_host(host: str, allow_private_ip: bool) -> bool:
    normalized = host.strip("[]").lower()
    if normalized in {"localhost", "ip6-localhost"}:
        return not allow_private_ip
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    if ip in METADATA_IPS:
        return True
    return (ip.is_private or ip.is_loopback or ip.is_link_local) and not allow_private_ip


def match_scope_pattern(target: str, host: str, pattern: str) -> bool:
    pattern = pattern.strip()
    if not pattern:
        return False

    if "://" in pattern:
        return fnmatch.fnmatch(target.rstrip("/"), pattern.rstrip("/"))

    if pattern.startswith("*."):
        suffix = pattern[1:].lower()
        return host.endswith(suffix) and host != pattern[2:].lower()

    parsed_pattern = parse_target(pattern)
    pattern_host = parsed_pattern["host"] or pattern.lower()
    if ":" in pattern and "://" not in pattern:
        return fnmatch.fnmatch(parse_target(target)["netloc"].lower(), pattern.lower())
    return fnmatch.fnmatch(host, pattern_host.lower())

