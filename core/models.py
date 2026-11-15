"""Typed data models shared by the monitoring services and GUI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class NetworkInterface:
    name: str
    is_up: bool
    ipv4_addresses: tuple[str, ...] = ()
    ipv6_addresses: tuple[str, ...] = ()
    mac_address: Optional[str] = None
    speed_mbps: Optional[int] = None
    mtu: Optional[int] = None


@dataclass(frozen=True, slots=True)
class NetworkInfo:
    hostname: str
    local_ip: Optional[str]
    public_ip: Optional[str]
    gateway: Optional[str]
    dns_servers: tuple[str, ...]
    connection_type: str
    active_interface: Optional[str]
    interfaces: tuple[NetworkInterface, ...]
    public_ip_error: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ConnectivityCheck:
    connected: bool
    latency_ms: Optional[float]
    method: str
    error: Optional[str] = None


@dataclass(frozen=True, slots=True)
class PingResult:
    target: str
    resolved_ip: Optional[str]
    sent: int
    received: int
    times_ms: tuple[float, ...] = ()
    times_display: tuple[str, ...] = ()
    loss_percent: Optional[float] = None
    error: Optional[str] = None
    command_output: str = ""

    @property
    def min_ms(self) -> Optional[float]:
        return min(self.times_ms) if self.times_ms else None

    @property
    def max_ms(self) -> Optional[float]:
        return max(self.times_ms) if self.times_ms else None

    @property
    def average_ms(self) -> Optional[float]:
        return sum(self.times_ms) / len(self.times_ms) if self.times_ms else None


@dataclass(frozen=True, slots=True)
class TrafficSample:
    download_bps: Optional[float]
    upload_bps: Optional[float]
    total_received_bytes: Optional[int]
    total_sent_bytes: Optional[int]


@dataclass(frozen=True, slots=True)
class NetworkSnapshot:
    timestamp: datetime
    internet_connected: bool
    internet_latency_ms: Optional[float]
    internet_method: str
    internet_error: Optional[str]
    download_bps: Optional[float]
    upload_bps: Optional[float]
    total_received_bytes: Optional[int]
    total_sent_bytes: Optional[int]
    packet_loss_percent: Optional[float]
    ping_latency_ms: Optional[float]
    probe_target: str
    probe_samples: int
    outage_count: int
    last_interruption: Optional[datetime]
    last_outage_duration_seconds: Optional[float]


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    key: str
    label: str
    status: str  # PASS, WARN, or FAIL
    detail: str
    recommendation: Optional[str] = None


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    generated_at: datetime
    checks: tuple[DiagnosticCheck, ...]
    summary: str
    recommendations: tuple[str, ...]
