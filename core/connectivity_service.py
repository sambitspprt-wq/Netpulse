"""Internet reachability checks using real HTTPS and TCP connections."""

from __future__ import annotations

import socket
import time

import requests

from core.models import ConnectivityCheck

_PRIMARY_URL = "https://connectivitycheck.gstatic.com/generate_204"
_MICROSOFT_URL = "https://www.msftconnecttest.com/connecttest.txt"


def check_internet(timeout: float = 2.5) -> ConnectivityCheck:
    """Check Internet reachability without relying on ICMP.

    A 204 from Google's connectivity endpoint or the expected Microsoft test
    text is considered a successful Internet response. If HTTPS checks cannot
    complete, a short external TCP/443 connection is tried. No result is cached.
    """
    timeout = max(0.5, min(float(timeout), 10.0))
    errors: list[str] = []
    start_all = time.monotonic()
    headers = {"User-Agent": "NetworkMonitor/1.0 (connectivity check)"}

    for index, url in enumerate((_PRIMARY_URL, _MICROSOFT_URL)):
        elapsed = time.monotonic() - start_all
        remaining = timeout - elapsed
        if remaining <= 0.15:
            break
        # Keep both requests bounded; together they stay close to the caller's
        # budget, even if a network has silently dropped outbound traffic.
        request_timeout = max(0.35, min(1.25, remaining / (2 - index)))
        started = time.monotonic()
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=request_timeout,
                allow_redirects=False,
            )
            latency = (time.monotonic() - started) * 1000.0
            if url == _PRIMARY_URL and response.status_code == 204:
                return ConnectivityCheck(True, latency, "HTTPS / Google 204")
            if url == _MICROSOFT_URL and response.status_code == 200:
                body = response.text.strip()
                if body == "Microsoft Connect Test":
                    return ConnectivityCheck(True, latency, "HTTPS / Microsoft test")
            errors.append(f"{url.split('/')[2]} returned HTTP {response.status_code}")
        except requests.RequestException as exc:
            errors.append(f"{url.split('/')[2]}: {exc.__class__.__name__}")

    # TCP reachability is a fallback for networks which block the test endpoint
    # but permit ordinary outbound TLS. It is not treated as a speed test.
    remaining = max(0.3, timeout - (time.monotonic() - start_all))
    tcp_timeout = min(1.0, remaining)
    started = time.monotonic()
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=tcp_timeout):
            latency = (time.monotonic() - started) * 1000.0
        return ConnectivityCheck(True, latency, "TCP / 1.1.1.1:443")
    except OSError as exc:
        errors.append(f"TCP fallback: {exc.__class__.__name__}")

    return ConnectivityCheck(
        False,
        None,
        "Unavailable",
        "; ".join(errors) if errors else "Connectivity test did not complete.",
    )
