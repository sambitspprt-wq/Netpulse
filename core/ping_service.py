"""Safe wrapper around the operating system's ping utility."""

from __future__ import annotations

import ipaddress
import math
import os
import re
import socket
import subprocess
from typing import Iterable

from core.models import PingResult

# Windows commonly prints ``time<1ms``; Unix normally prints ``time=0.8 ms``.
_RTT_PATTERN = re.compile(r"\btime\s*([=<])\s*(\d+(?:[.,]\d+)?)\s*ms\b", re.IGNORECASE)
_DNS_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def validate_target(target: str) -> str:
    """Validate and normalize an IPv4/IPv6 address or DNS hostname.

    Shell metacharacters and option-like targets are rejected even though the
    command is invoked without a shell. This keeps the UI's target contract clear
    and avoids passing ping options in place of a host.
    """
    value = (target or "").strip().rstrip(".")
    if not value:
        raise ValueError("Enter an IP address or hostname.")
    if value.startswith("-") or any(ch.isspace() for ch in value):
        raise ValueError("Enter a valid IP address or hostname without spaces.")

    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass

    try:
        hostname = value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("The hostname is not valid.") from exc

    if len(hostname) > 253:
        raise ValueError("The hostname is too long.")
    labels = hostname.split(".")
    if not labels or any(not _DNS_LABEL_PATTERN.fullmatch(label) for label in labels):
        raise ValueError("Enter a valid IP address or hostname.")
    return hostname


def _extract_ping_samples(output: str) -> tuple[tuple[float, ...], tuple[str, ...]]:
    """Extract numeric RTT bounds and faithful display labels from ping output."""
    values: list[float] = []
    labels: list[str] = []
    for line in output.splitlines():
        match = _RTT_PATTERN.search(line)
        if not match:
            continue
        operator, raw_number = match.groups()
        number = raw_number.replace(",", ".")
        try:
            value = float(number)
        except ValueError:
            continue
        values.append(value)
        labels.append(f"< {value:g} ms" if operator == "<" else f"{value:g} ms")
    return tuple(values), tuple(labels)


def _extract_ping_times(output: str) -> tuple[float, ...]:
    """Extract numeric RTT values (bounds for replies rounded by the OS)."""
    return _extract_ping_samples(output)[0]


def _resolve_target(target: str) -> tuple[str, int]:
    """Resolve an address, preferring IPv4 for hostnames when available."""
    try:
        address = ipaddress.ip_address(target)
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        return str(address), family
    except ValueError:
        pass

    last_error: socket.gaierror | None = None
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            info = socket.getaddrinfo(
                target, None, family=family, type=socket.SOCK_DGRAM
            )
            if info:
                return info[0][4][0], family
        except socket.gaierror as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise socket.gaierror(f"No IP address found for {target}")


def _ping_command(target: str, count: int, timeout_ms: int, family: int) -> list[str]:
    family_flag = "-6" if family == socket.AF_INET6 else "-4"
    if os.name == "nt":
        return ["ping", family_flag, "-n", str(count), "-w", str(timeout_ms), target]
    # Linux and macOS accept -c and -W. The system ping utility has second-level
    # timeout granularity on several Unix variants, so round up safely.
    timeout_seconds = max(1, math.ceil(timeout_ms / 1000))
    return ["ping", family_flag, "-c", str(count), "-W", str(timeout_seconds), target]


def ping_host(target: str, count: int = 4, timeout_ms: int = 1200) -> PingResult:
    """Ping a host and return measured replies, RTTs, and packet loss.

    ICMP can be filtered by a router, VPN, firewall, or destination. A missing
    reply therefore means "no ICMP reply received" rather than proof that a host
    or the Internet is offline.
    """
    normalized = validate_target(target)
    if not 1 <= int(count) <= 50:
        raise ValueError("Ping count must be between 1 and 50.")
    if not 250 <= int(timeout_ms) <= 10000:
        raise ValueError("Ping timeout must be between 250 and 10000 milliseconds.")
    count = int(count)
    timeout_ms = int(timeout_ms)

    try:
        resolved_ip, address_family = _resolve_target(normalized)
    except socket.gaierror as exc:
        message = f"DNS resolution failed for {normalized}: {exc}"
        return PingResult(
            target=normalized,
            resolved_ip=None,
            sent=count,
            received=0,
            loss_percent=100.0,
            error=message,
        )

    command = _ping_command(resolved_ip, count, timeout_ms, address_family)
    overall_timeout = max(3.0, count * timeout_ms / 1000.0 + 2.5)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=overall_timeout,
            check=False,
            creationflags=creationflags,
        )
        output = "\n".join(
            part for part in (completed.stdout, completed.stderr) if part
        ).strip()
    except FileNotFoundError:
        return PingResult(
            target=normalized,
            resolved_ip=resolved_ip,
            sent=count,
            received=0,
            loss_percent=100.0,
            error="The system ping utility was not found. Check that ping is available on PATH.",
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or b""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        times, labels = _extract_ping_samples(str(partial))
        received = min(len(times), count)
        return PingResult(
            target=normalized,
            resolved_ip=resolved_ip,
            sent=count,
            received=received,
            times_ms=times[:count],
            times_display=labels[:count],
            loss_percent=(count - received) * 100.0 / count,
            error="Ping process exceeded its safety timeout.",
            command_output=str(partial),
        )
    except OSError as exc:
        return PingResult(
            target=normalized,
            resolved_ip=resolved_ip,
            sent=count,
            received=0,
            loss_percent=100.0,
            error=f"Could not run ping: {exc}",
        )

    times, labels = _extract_ping_samples(output)
    times = times[:count]
    labels = labels[:count]
    received = len(times)
    loss = (count - received) * 100.0 / count
    error = (
        None
        if received
        else "No ICMP replies received; the host may be offline or ICMP may be filtered."
    )
    return PingResult(
        target=normalized,
        resolved_ip=resolved_ip,
        sent=count,
        received=received,
        times_ms=times,
        times_display=labels,
        loss_percent=loss,
        error=error,
        command_output=output,
    )


def extract_ping_times(lines: Iterable[str]) -> tuple[float, ...]:
    """Public, small numeric parsing helper used by the test suite."""
    return _extract_ping_times("\n".join(lines))


def extract_ping_samples(
    lines: Iterable[str],
) -> tuple[tuple[float, ...], tuple[str, ...]]:
    """Return numeric RTT bounds and display strings for ping reply lines."""
    return _extract_ping_samples("\n".join(lines))
