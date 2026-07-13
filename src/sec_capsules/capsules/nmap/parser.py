from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from sec_capsules.core.artifacts import artifact_ref


def parse(raw_text: str, *, run_id: str, artifact_name: str) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    services: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    hosts = _completed_hosts(raw_text)
    port_lines = iter(_element_lines(raw_text, "port"))

    for host in hosts:
        status = host.find("status")
        if status is not None and status.get("state") != "up":
            continue
        address = _primary_address(host)
        if not address:
            continue

        hostnames = sorted(
            {
                item.get("name", "")
                for item in host.findall("./hostnames/hostname")
                if item.get("name")
            }
        )
        address_line = _address_line(raw_text, address)
        address_ref = artifact_ref(run_id, artifact_name, address_line)
        assets.append(
            {
                "type": "asset.v1",
                "value": address,
                "kind": "host",
                "hostnames": hostnames,
                "source_tool": "nmap",
                "evidence_refs": [address_ref],
            }
        )
        evidence.append(
            {
                "type": "evidence.v1",
                "source_tool": "nmap",
                "artifact_ref": address_ref,
                "summary": f"Nmap reported host {address} as up",
            }
        )

        for port in host.findall("./ports/port"):
            line_no = next(port_lines, 1)
            state_node = port.find("state")
            state = state_node.get("state", "unknown") if state_node is not None else "unknown"
            if state != "open":
                continue
            service_node = port.find("service")
            service_node = service_node if service_node is not None else ET.Element("service")
            protocol = port.get("protocol", "tcp")
            port_number = int(port.get("portid", "0"))
            service_ref = artifact_ref(run_id, artifact_name, line_no)
            service = {
                "type": "service.v1",
                "host": address,
                "port": port_number,
                "protocol": protocol,
                "state": state,
                "name": service_node.get("name"),
                "product": service_node.get("product"),
                "version": service_node.get("version"),
                "extra_info": service_node.get("extrainfo"),
                "tunnel": service_node.get("tunnel"),
                "confidence": _integer_or_none(service_node.get("conf")),
                "cpes": [item.text for item in service_node.findall("cpe") if item.text],
                "source_tool": "nmap",
                "evidence_refs": [service_ref],
            }
            url = _service_url(address, port_number, service_node)
            if url:
                service["url"] = url
            services.append(service)
            evidence.append(
                {
                    "type": "evidence.v1",
                    "source_tool": "nmap",
                    "artifact_ref": service_ref,
                    "summary": (
                        f"Nmap reported open {protocol}/{port_number} on {address}"
                        f" as {service_node.get('name') or 'unknown'}"
                    ),
                }
            )

    return {
        "assets": assets,
        "services": services,
        "endpoints": [],
        "findings": [],
        "evidence": evidence,
    }


def _completed_hosts(raw_text: str) -> list[ET.Element]:
    parser = ET.XMLPullParser(events=("end",))
    hosts: list[ET.Element] = []
    for line in raw_text.splitlines(keepends=True):
        try:
            parser.feed(line)
            events = list(parser.read_events())
        except ET.ParseError:
            break
        for _, element in events:
            if element.tag == "host":
                hosts.append(element)
    return hosts


def _primary_address(host: ET.Element) -> str:
    addresses = host.findall("address")
    for address_type in ("ipv4", "ipv6"):
        for item in addresses:
            if item.get("addrtype") == address_type and item.get("addr"):
                return str(item.get("addr"))
    return ""


def _element_lines(raw_text: str, name: str) -> list[int]:
    pattern = re.compile(rf"<{re.escape(name)}(?:\s|>)")
    return [
        line_no
        for line_no, line in enumerate(raw_text.splitlines(), start=1)
        if pattern.search(line)
    ]


def _address_line(raw_text: str, address: str) -> int:
    quoted = re.compile(rf"<address\b[^>]*\baddr=[\"']{re.escape(address)}[\"']")
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        if quoted.search(line):
            return line_no
    return 1


def _integer_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _service_url(host: str, port: int, service: ET.Element) -> str | None:
    name = (service.get("name") or "").lower()
    tunnel = (service.get("tunnel") or "").lower()
    if name not in {"http", "http-proxy", "https", "ssl/http"} and tunnel != "ssl":
        return None
    scheme = "https" if name in {"https", "ssl/http"} or tunnel == "ssl" else "http"
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    return f"{scheme}://{host}" if default_port else f"{scheme}://{host}:{port}"
