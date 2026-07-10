from __future__ import annotations

import fnmatch
import ipaddress
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlparse

import yaml


METADATA_IPS = {
    ipaddress.ip_address("100.100.100.200"),
    ipaddress.ip_address("169.254.0.23"),
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
    ipaddress.ip_address("fe80::a9fe:a9fe"),
}

Resolver = Callable[[str], list[str]]


@dataclass
class ScopeDecision:
    allowed: bool
    reasons: list[str]
    target: str = ""
    normalized_target: str = ""
    resolved_addresses: list[str] = field(default_factory=list)
    approval: dict[str, object] = field(default_factory=dict)

    def raise_if_denied(self) -> None:
        if not self.allowed:
            raise PermissionError("; ".join(self.reasons))

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reasons": self.reasons,
            "target": self.target,
            "normalized_target": self.normalized_target,
            "resolved_addresses": self.resolved_addresses,
            "approval": self.approval,
        }


class ScopePolicy:
    def __init__(self, raw: dict, *, resolver: Resolver | None = None) -> None:
        scope = raw.get("scope", raw)
        self.include = list(scope.get("include", []))
        self.exclude = list(scope.get("exclude", []))
        self.max_requests_per_minute = int(scope.get("max_requests_per_minute", 60))
        self.allow_private_ip = bool(scope.get("allow_private_ip", False))
        self.allow_active_scan = bool(scope.get("allow_active_scan", False))
        self.require_approval_for = set(scope.get("require_approval_for", []))
        self.resolver = resolver or resolve_host

    @classmethod
    def from_file(cls, path: str | Path) -> "ScopePolicy":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(raw)

    @staticmethod
    def approval_from_file(path: str | Path) -> dict:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        value = raw.get("approval", raw)
        if not isinstance(value, dict):
            raise ValueError("approval file must contain an object")
        return value

    def decide(
        self,
        target: str,
        action: str | None = None,
        active: bool = False,
        requested_rate_limit: int | None = None,
        requires_approval: bool = False,
        approval: dict | None = None,
        resolve_dns: bool = False,
    ) -> ScopeDecision:
        reasons: list[str] = []
        parsed = parse_target(target)
        host = parsed["host"]
        normalized_target = parsed["normalized_target"]
        resolved_addresses: list[str] = []

        if not host:
            reasons.append(f"target has no host: {target}")

        if active and not self.allow_active_scan:
            reasons.append("active scan is not allowed by scope policy")

        if requested_rate_limit is not None and requested_rate_limit > self.max_requests_per_minute:
            reasons.append(
                f"requested rate limit {requested_rate_limit} exceeds scope maximum "
                f"{self.max_requests_per_minute}"
            )

        should_resolve = host and resolve_dns and (
            not self.include
            or any(_is_network_pattern(pattern) for pattern in [*self.include, *self.exclude])
            or any(match_scope_pattern(target, host, pattern) for pattern in self.include)
        )
        if should_resolve:
            try:
                resolved_addresses = self.resolver(host)
            except OSError as exc:
                reasons.append(f"target host could not be resolved: {host} ({exc})")
            else:
                if not resolved_addresses:
                    reasons.append(f"target host resolved to no addresses: {host}")

        if host and self.include and not any(
            match_scope_pattern(target, host, pattern, resolved_addresses) for pattern in self.include
        ):
            reasons.append(f"target is not included in scope: {target}")

        if host and any(match_scope_pattern(target, host, pattern, resolved_addresses) for pattern in self.exclude):
            reasons.append(f"target is excluded by scope policy: {target}")

        if host and is_blocked_private_host(host, self.allow_private_ip):
            reasons.append(f"private or metadata host is not allowed: {host}")

        for address in resolved_addresses:
            if is_blocked_private_host(address, self.allow_private_ip):
                reasons.append(f"resolved address is private or metadata and not allowed: {address}")

        approval_required = requires_approval or bool(action and action in self.require_approval_for)
        approval_summary: dict[str, object] = {"required": approval_required, "approved": False}
        if approval_required:
            approval_reasons, approval_summary = validate_approval(
                approval,
                action=action or "",
                target=target,
                host=host,
            )
            reasons.extend(approval_reasons)

        return ScopeDecision(
            allowed=not reasons,
            reasons=reasons,
            target=target,
            normalized_target=normalized_target,
            resolved_addresses=sorted(set(resolved_addresses)),
            approval=approval_summary,
        )


def parse_target(target: str) -> dict[str, str]:
    value = target.strip()
    parsed = urlparse(value if "://" in value else f"//{value}", scheme="http")
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError:
        port = None
    scheme = (parsed.scheme or "http").lower()
    host_for_netloc = f"[{host}]" if ":" in host and not host.startswith("[") else host
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host_for_netloc if port is None or default_port else f"{host_for_netloc}:{port}"
    path = parsed.path or "/"
    normalized_target = f"{scheme}://{netloc}{path}"
    if parsed.query:
        normalized_target = f"{normalized_target}?{parsed.query}"
    return {
        "scheme": scheme,
        "host": host,
        "netloc": netloc,
        "path": path,
        "normalized_target": normalized_target,
    }


def resolve_host(host: str) -> list[str]:
    normalized = host.strip("[]")
    try:
        return [str(ipaddress.ip_address(normalized))]
    except ValueError:
        pass
    addresses = {
        item[4][0]
        for item in socket.getaddrinfo(normalized, None, type=socket.SOCK_STREAM)
        if item[4]
    }
    return sorted(addresses)


def is_blocked_private_host(host: str, allow_private_ip: bool) -> bool:
    normalized = host.strip("[]").lower()
    if normalized in {"localhost", "ip6-localhost"}:
        return not allow_private_ip
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    if address in METADATA_IPS:
        return True
    if address.is_unspecified or address.is_multicast:
        return True
    if address.is_reserved and not (address.is_private or address.is_loopback or address.is_link_local):
        return True
    return (address.is_private or address.is_loopback or address.is_link_local) and not allow_private_ip


def match_scope_pattern(
    target: str,
    host: str,
    pattern: str,
    resolved_addresses: Iterable[str] = (),
) -> bool:
    pattern = pattern.strip()
    if not pattern:
        return False

    try:
        network = ipaddress.ip_network(pattern, strict=False)
    except ValueError:
        network = None
    if network is not None:
        candidates = [host, *resolved_addresses]
        for candidate in candidates:
            try:
                if ipaddress.ip_address(candidate.strip("[]")) in network:
                    return True
            except ValueError:
                continue
        return False

    if "://" in pattern:
        return fnmatch.fnmatch(parse_target(target)["normalized_target"].rstrip("/"), pattern.rstrip("/"))

    if pattern.startswith("*."):
        suffix = pattern[1:].lower()
        return host.endswith(suffix) and host != pattern[2:].lower()

    parsed_pattern = parse_target(pattern)
    pattern_host = parsed_pattern["host"] or pattern.lower()
    if ":" in pattern and "://" not in pattern:
        return fnmatch.fnmatch(parse_target(target)["netloc"].lower(), pattern.lower())
    return fnmatch.fnmatch(host, pattern_host.lower())


def _is_network_pattern(pattern: str) -> bool:
    try:
        ipaddress.ip_network(pattern.strip(), strict=False)
    except ValueError:
        return False
    return True


def validate_approval(
    approval: dict | None,
    *,
    action: str,
    target: str,
    host: str,
) -> tuple[list[str], dict[str, object]]:
    if not approval:
        return [f"action {action!r} requires an approval record"], {"required": True, "approved": False}

    actions = approval.get("actions", [])
    if isinstance(actions, str):
        actions = [actions]
    targets = approval.get("targets", approval.get("target", []))
    if isinstance(targets, str):
        targets = [targets]

    summary: dict[str, object] = {
        "required": True,
        "approved": False,
        "approval_id": approval.get("id"),
        "approved_by": approval.get("approved_by"),
        "actions": list(actions),
    }
    reasons: list[str] = []
    if not approval.get("id") or not approval.get("approved_by"):
        reasons.append("approval record must include id and approved_by")
    if action not in actions:
        reasons.append(f"approval record does not allow action {action!r}")
    if not targets:
        reasons.append("approval record must bind one or more targets")
    elif not any(match_scope_pattern(target, host, str(pattern)) for pattern in targets):
        reasons.append(f"approval record does not allow target {target!r}")

    if not reasons:
        summary["approved"] = True
    return reasons, summary
