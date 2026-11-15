"""On-demand network diagnostics and human-readable troubleshooting guidance."""

from __future__ import annotations

import socket
from datetime import datetime

from core.connectivity_service import check_internet
from core.models import DiagnosticCheck, DiagnosticReport
from core.network_info_service import get_network_info
from core.ping_service import ping_host


def diagnose_network() -> DiagnosticReport:
    """Run adapter, gateway, DNS, and Internet checks in the calling thread.

    The GUI calls this function from its background worker pool so DNS and ICMP
    timeouts never block the Tk event loop.
    """
    checks: list[DiagnosticCheck] = []
    recommendations: list[str] = []
    info = get_network_info(include_public=False)

    active_interface = next(
        (
            interface
            for interface in info.interfaces
            if interface.name == info.active_interface
        ),
        None,
    )
    if info.local_ip and not info.local_ip.startswith("169.254."):
        adapter_name = info.active_interface or "active adapter"
        checks.append(
            DiagnosticCheck(
                "adapter",
                "Local network adapter",
                "PASS",
                f"{adapter_name} has local IPv4 address {info.local_ip}.",
            )
        )
    elif info.local_ip:
        message = "A link-local IPv4 address was found; DHCP may not have assigned a normal address."
        checks.append(
            DiagnosticCheck(
                "adapter",
                "Local network adapter",
                "WARN",
                message,
                "Reconnect to Wi-Fi or Ethernet, then renew the DHCP lease or restart the router.",
            )
        )
        recommendations.append(
            "Reconnect to Wi-Fi or Ethernet, then renew the DHCP lease or restart the router."
        )
    elif active_interface and active_interface.is_up:
        message = f"{active_interface.name} is up, but no usable local IPv4 address was found."
        checks.append(
            DiagnosticCheck(
                "adapter",
                "Local network adapter",
                "FAIL",
                message,
                "Check the adapter connection and obtain an address from the router (DHCP).",
            )
        )
        recommendations.append(
            "Check the adapter connection and obtain an address from the router (DHCP)."
        )
    else:
        message = "No active adapter with a usable local IPv4 address was detected."
        checks.append(
            DiagnosticCheck(
                "adapter",
                "Local network adapter",
                "FAIL",
                message,
                "Enable the Wi-Fi/Ethernet adapter and connect to a network.",
            )
        )
        recommendations.append(
            "Enable the Wi-Fi/Ethernet adapter and connect to a network."
        )

    gateway_reachable = False
    if info.gateway:
        gateway_ping = ping_host(info.gateway, count=2, timeout_ms=900)
        gateway_reachable = gateway_ping.received > 0
        if gateway_reachable:
            checks.append(
                DiagnosticCheck(
                    "gateway",
                    "Default gateway",
                    "PASS",
                    f"Gateway {info.gateway} replied to {gateway_ping.received} of {gateway_ping.sent} ICMP probes.",
                )
            )
        else:
            detail = (
                f"Gateway {info.gateway} did not reply to ICMP. Some routers block ping, "
                "so this alone does not prove the local network is down."
            )
            checks.append(
                DiagnosticCheck(
                    "gateway",
                    "Default gateway",
                    "WARN",
                    detail,
                    "Compare this with the separate Internet check; some gateways intentionally ignore ICMP.",
                )
            )
    else:
        checks.append(
            DiagnosticCheck(
                "gateway",
                "Default gateway",
                "FAIL",
                "No default IPv4 gateway was found in the system route table.",
                "Reconnect to the network and renew the DHCP lease; check the router or network profile.",
            )
        )
        recommendations.append(
            "Reconnect to the network and renew the DHCP lease; check the router or network profile."
        )

    dns_ok = False
    resolved_addresses: list[str] = []
    try:
        answers = socket.getaddrinfo(
            "example.com", 443, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
        resolved_addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
        dns_ok = bool(resolved_addresses)
    except socket.gaierror as exc:
        dns_error = exc.strerror or str(exc)
    else:
        dns_error = "No IPv4 answers were returned."

    if dns_ok:
        dns_summary = ", ".join(resolved_addresses[:2])
        configured_dns = (
            ", ".join(info.dns_servers) if info.dns_servers else "system resolver"
        )
        checks.append(
            DiagnosticCheck(
                "dns",
                "DNS resolution",
                "PASS",
                f"example.com resolved to {dns_summary}; configured DNS: {configured_dns}.",
            )
        )
    else:
        dns_summary = (
            ", ".join(info.dns_servers) if info.dns_servers else "no DNS server listed"
        )
        detail = f"Could not resolve example.com ({dns_error}); configured DNS: {dns_summary}."
        recommendation = "Check the configured DNS servers; if permitted, try your router DNS or a trusted resolver such as 1.1.1.1."
        checks.append(
            DiagnosticCheck("dns", "DNS resolution", "FAIL", detail, recommendation)
        )
        recommendations.append(recommendation)

    internet = check_internet(timeout=3.0)
    if internet.connected:
        checks.append(
            DiagnosticCheck(
                "internet",
                "Internet reachability",
                "PASS",
                f"An external connection succeeded using {internet.method}"
                + (
                    f" in {internet.latency_ms:.0f} ms."
                    if internet.latency_ms is not None
                    else "."
                ),
            )
        )
    else:
        detail = (
            "The HTTPS connectivity tests and external TCP fallback did not complete."
        )
        recommendation = (
            "Check for a captive-portal sign-in, VPN/proxy rules, firewall restrictions, "
            "or an ISP/router outage."
        )
        checks.append(
            DiagnosticCheck(
                "internet", "Internet reachability", "FAIL", detail, recommendation
            )
        )
        recommendations.append(recommendation)

    if (
        internet.connected
        and dns_ok
        and gateway_reachable
        and info.local_ip
        and info.gateway
    ):
        summary = (
            "All end-to-end checks passed. No common connectivity problem was detected."
        )
    elif not info.local_ip or not info.gateway:
        summary = "A local network configuration problem is likely; start with the adapter and gateway checks."
    elif not internet.connected:
        summary = "Local connectivity may be present, but Internet reachability failed. Review DNS, gateway, and upstream access."
    else:
        summary = "The Internet is reachable, but one or more supporting checks need attention."

    # Preserve order while avoiding repeated guidance from related checks.
    unique_recommendations = tuple(dict.fromkeys(recommendations))
    if not unique_recommendations:
        unique_recommendations = (
            "If a particular app or host still fails, test that destination separately and check its firewall/proxy rules.",
        )
    return DiagnosticReport(
        generated_at=datetime.now().astimezone(),
        checks=tuple(checks),
        summary=summary,
        recommendations=unique_recommendations,
    )
