"""Cross-platform network interface, gateway, DNS, and IP information."""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import struct
import subprocess
from pathlib import Path
from typing import Optional

import psutil
import requests

from core.models import NetworkInfo, NetworkInterface


def _run_command(args: list[str], timeout: float = 3.0) -> str:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=creationflags,
    )
    return completed.stdout or ""


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip())
        return True
    except ValueError:
        return False


def _collect_interfaces() -> tuple[NetworkInterface, ...]:
    try:
        addresses_by_name = psutil.net_if_addrs()
        stats_by_name = psutil.net_if_stats()
    except (OSError, RuntimeError):
        return ()

    link_families = {
        getattr(psutil, "AF_LINK", object()),
        getattr(socket, "AF_PACKET", object()),
    }
    interfaces: list[NetworkInterface] = []
    for name, addresses in addresses_by_name.items():
        ipv4: list[str] = []
        ipv6: list[str] = []
        mac: Optional[str] = None
        for address in addresses:
            value = str(getattr(address, "address", "") or "").split("%", 1)[0]
            family = getattr(address, "family", None)
            if family == socket.AF_INET and _is_ip(value):
                ipv4.append(value)
            elif family == socket.AF_INET6 and _is_ip(value):
                ipv6.append(value)
            elif family in link_families and value and not mac:
                # A few platforms expose an empty or placeholder link-layer
                # address; skip those rather than displaying misleading data.
                if value not in {"00:00:00:00:00:00", "00-00-00-00-00-00"}:
                    mac = value

        stats = stats_by_name.get(name)
        speed = getattr(stats, "speed", 0) if stats else 0
        mtu = getattr(stats, "mtu", 0) if stats else 0
        interfaces.append(
            NetworkInterface(
                name=name,
                is_up=bool(getattr(stats, "isup", False)),
                ipv4_addresses=tuple(dict.fromkeys(ipv4)),
                ipv6_addresses=tuple(dict.fromkeys(ipv6)),
                mac_address=mac,
                speed_mbps=int(speed) if speed and speed > 0 else None,
                mtu=int(mtu) if mtu and mtu > 0 else None,
            )
        )
    return tuple(
        sorted(
            interfaces, key=lambda item: (item.name.lower() == "lo", item.name.lower())
        )
    )


def _windows_default_gateway() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return gateway, route interface name (if known), and interface IPv4."""
    output = _run_command(["route", "print", "-4"])
    routes: list[tuple[int, str, Optional[str]]] = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[0] != "0.0.0.0" or fields[1] != "0.0.0.0":
            continue
        gateway, interface_ip = fields[2], fields[3]
        if not _is_ip(gateway):
            continue
        try:
            metric = int(fields[4])
        except ValueError:
            metric = 1_000_000
        routes.append((metric, gateway, interface_ip if _is_ip(interface_ip) else None))
    if not routes:
        return None, None, None
    _, gateway, interface_ip = min(routes, key=lambda route: route[0])
    return gateway, None, interface_ip


def _unix_default_gateway() -> tuple[Optional[str], Optional[str], Optional[str]]:
    if os.name == "posix" and Path("/proc/net/route").exists():
        try:
            lines = (
                Path("/proc/net/route")
                .read_text(encoding="ascii", errors="ignore")
                .splitlines()[1:]
            )
            candidates: list[tuple[int, str, str]] = []
            for line in lines:
                fields = line.split()
                if len(fields) < 4 or fields[1] != "00000000":
                    continue
                try:
                    flags = int(fields[3], 16)
                    gateway_num = int(fields[2], 16)
                    metric = int(fields[6]) if len(fields) > 6 else 0
                except ValueError:
                    continue
                if not (flags & 0x1):
                    continue
                gateway = socket.inet_ntoa(struct.pack("<I", gateway_num))
                if gateway != "0.0.0.0":
                    candidates.append((metric, gateway, fields[0]))
            if candidates:
                _, gateway, interface_name = min(candidates, key=lambda route: route[0])
                return gateway, interface_name, None
        except (OSError, IndexError):
            pass

    try:
        output = _run_command(["ip", "-4", "route", "show", "default"])
        for line in output.splitlines():
            fields = line.split()
            gateway: Optional[str] = None
            interface_name: Optional[str] = None
            for index, token in enumerate(fields[:-1]):
                if token == "via" and _is_ip(fields[index + 1]):
                    gateway = fields[index + 1]
                elif token == "dev":
                    interface_name = fields[index + 1]
            if gateway:
                return gateway, interface_name, None
    except (OSError, subprocess.SubprocessError):
        pass

    if hasattr(os, "uname") and os.uname().sysname.lower() == "darwin":
        try:
            output = _run_command(["route", "-n", "get", "default"])
            gateway = None
            interface_name = None
            for line in output.splitlines():
                if ":" not in line:
                    continue
                key, value = (part.strip() for part in line.split(":", 1))
                if key == "gateway" and _is_ip(value):
                    gateway = value
                elif key == "interface":
                    interface_name = value
            if gateway:
                return gateway, interface_name, None
        except (OSError, subprocess.SubprocessError):
            pass
    return None, None, None


def get_default_gateway() -> tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        if os.name == "nt":
            return _windows_default_gateway()
        return _unix_default_gateway()
    except (OSError, subprocess.SubprocessError, ValueError):
        return None, None, None


def _choose_local_ip(
    interfaces: tuple[NetworkInterface, ...],
    route_interface: Optional[str],
    route_ip: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    if route_interface:
        for interface in interfaces:
            if interface.name == route_interface and interface.ipv4_addresses:
                return interface.ipv4_addresses[0], interface.name
    if route_ip:
        for interface in interfaces:
            if route_ip in interface.ipv4_addresses:
                return route_ip, interface.name

    # A UDP connect selects the OS's preferred outbound source address. It does
    # not send an application payload and generally works even behind a router.
    probe: Optional[socket.socket] = None
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(1.0)
        probe.connect(("1.1.1.1", 53))
        local_ip = probe.getsockname()[0]
        if _is_ip(local_ip) and not local_ip.startswith("127."):
            for interface in interfaces:
                if local_ip in interface.ipv4_addresses:
                    return local_ip, interface.name
            return local_ip, None
    except OSError:
        pass
    finally:
        if probe is not None:
            probe.close()

    for interface in interfaces:
        if interface.is_up:
            for address in interface.ipv4_addresses:
                if not address.startswith("127.") and not address.startswith(
                    "169.254."
                ):
                    return address, interface.name
    return None, None


def _split_ip_values(value: object) -> list[str]:
    if isinstance(value, (tuple, list)):
        raw_values = [str(item) for item in value]
    else:
        raw_values = re.split(r"[,;\s\x00]+", str(value or ""))
    results: list[str] = []
    for item in raw_values:
        candidate = item.strip().strip("\x00")
        if candidate and _is_ip(candidate):
            results.append(str(ipaddress.ip_address(candidate)))
    return results


def _windows_dns_servers(active_ips: set[str]) -> tuple[str, ...]:
    preferred: list[str] = []
    other: list[str] = []
    try:
        import winreg  # type: ignore[import-not-found]  # Windows only

        root_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root_path) as root:
            count = winreg.QueryInfoKey(root)[0]
            for index in range(count):
                try:
                    interface_id = winreg.EnumKey(root, index)
                    with winreg.OpenKey(root, interface_id) as interface_key:
                        assigned: set[str] = set()
                        for name in ("IPAddress", "DhcpIPAddress"):
                            try:
                                assigned.update(
                                    _split_ip_values(
                                        winreg.QueryValueEx(interface_key, name)[0]
                                    )
                                )
                            except OSError:
                                continue
                        static_dns: list[str] = []
                        dhcp_dns: list[str] = []
                        for name, destination in (
                            ("NameServer", static_dns),
                            ("DhcpNameServer", dhcp_dns),
                        ):
                            try:
                                destination.extend(
                                    _split_ip_values(
                                        winreg.QueryValueEx(interface_key, name)[0]
                                    )
                                )
                            except OSError:
                                continue
                        servers = static_dns or dhcp_dns
                        if not servers:
                            continue
                        if active_ips and assigned.intersection(active_ips):
                            preferred.extend(servers)
                        else:
                            other.extend(servers)
                except OSError:
                    continue
    except (ImportError, OSError):
        pass

    return tuple(dict.fromkeys(preferred or other))


def _ipconfig_dns_fallback() -> tuple[str, ...]:
    try:
        output = _run_command(["ipconfig", "/all"])
    except (OSError, subprocess.SubprocessError):
        return ()
    servers: list[str] = []
    collecting = False
    for line in output.splitlines():
        if re.search(r"\bDNS Servers?\b", line, re.IGNORECASE):
            collecting = True
            _, separator, value = line.partition(":")
            if separator:
                servers.extend(_split_ip_values(value))
            continue
        if collecting:
            if line[:1].isspace() and ":" not in line:
                servers.extend(_split_ip_values(line))
            else:
                collecting = False
    return tuple(dict.fromkeys(servers))


def _get_dns_servers(active_ips: set[str]) -> tuple[str, ...]:
    if os.name == "nt":
        servers = _windows_dns_servers(active_ips)
        return servers or _ipconfig_dns_fallback()

    servers: list[str] = []
    try:
        for line in (
            Path("/etc/resolv.conf")
            .read_text(encoding="utf-8", errors="ignore")
            .splitlines()
        ):
            parts = line.split()
            if (
                len(parts) >= 2
                and parts[0].lower() == "nameserver"
                and _is_ip(parts[1])
            ):
                servers.append(str(ipaddress.ip_address(parts[1])))
    except OSError:
        pass
    return tuple(dict.fromkeys(servers))


def _connection_type(interface_name: Optional[str]) -> str:
    if not interface_name:
        return "Unknown"
    name = interface_name.lower()
    if any(
        token in name for token in ("wi-fi", "wifi", "wireless", "wlan", "airport")
    ) or name.startswith(("wl", "wifi")):
        return "Wi-Fi"
    if any(
        token in name for token in ("ethernet", "ether", "local area", "lan")
    ) or name.startswith(("eth", "enp", "eno", "enx")):
        return "Ethernet"
    if any(
        token in name
        for token in ("vpn", "tunnel", "virtual", "tap", "tun", "loopback")
    ):
        return "Virtual / VPN"
    return "Other / unknown"


def _public_ip_lookup(timeout: float = 3.0) -> tuple[Optional[str], Optional[str]]:
    try:
        response = requests.get(
            "https://api.ipify.org",
            timeout=timeout,
            headers={"User-Agent": "NetworkMonitor/1.0"},
        )
        response.raise_for_status()
        value = response.text.strip()
        if not _is_ip(value):
            return None, "The public IP service returned an invalid response."
        return str(ipaddress.ip_address(value)), None
    except requests.RequestException as exc:
        return None, f"Public IP lookup failed ({exc.__class__.__name__})."


def get_network_info(include_public: bool = True) -> NetworkInfo:
    """Collect current adapter and network configuration information."""
    interfaces = _collect_interfaces()
    gateway, route_interface, route_ip = get_default_gateway()
    local_ip, active_interface = _choose_local_ip(interfaces, route_interface, route_ip)

    if active_interface is None and route_interface:
        active_interface = route_interface
    active_ips = {local_ip} if local_ip else set()
    dns_servers = _get_dns_servers(active_ips)
    connection_type = _connection_type(active_interface)

    public_ip: Optional[str] = None
    public_ip_error: Optional[str] = None
    if include_public:
        public_ip, public_ip_error = _public_ip_lookup()

    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = "Unknown"

    return NetworkInfo(
        hostname=hostname,
        local_ip=local_ip,
        public_ip=public_ip,
        gateway=gateway,
        dns_servers=dns_servers,
        connection_type=connection_type,
        active_interface=active_interface,
        interfaces=interfaces,
        public_ip_error=public_ip_error,
    )
