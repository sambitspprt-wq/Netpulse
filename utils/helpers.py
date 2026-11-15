"""Formatting helpers for measured values and timestamps."""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def format_speed(bytes_per_second: Optional[float]) -> str:
    if bytes_per_second is None:
        return "—"
    bits_per_second = max(0.0, float(bytes_per_second)) * 8.0
    if bits_per_second >= 1_000_000_000:
        return f"{bits_per_second / 1_000_000_000:.2f} Gbps"
    if bits_per_second >= 1_000_000:
        return f"{bits_per_second / 1_000_000:.2f} Mbps"
    if bits_per_second >= 1_000:
        return f"{bits_per_second / 1_000:.1f} Kbps"
    return f"{bits_per_second:.0f} bps"


def format_bytes(byte_count: Optional[int]) -> str:
    if byte_count is None:
        return "—"
    value = float(max(0, int(byte_count)))
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def format_latency(milliseconds: Optional[float]) -> str:
    if milliseconds is None:
        return "—"
    if milliseconds < 1:
        return f"{milliseconds:.2f} ms"
    if milliseconds < 100:
        return f"{milliseconds:.1f} ms"
    return f"{milliseconds:.0f} ms"


def format_loss(percent: Optional[float]) -> str:
    if percent is None:
        return "—"
    return f"{percent:.1f}%"


def format_timestamp(value: Optional[datetime]) -> str:
    if value is None:
        return "—"
    try:
        return value.astimezone().strftime("%H:%M:%S")
    except (ValueError, OSError):
        return value.strftime("%H:%M:%S")


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(seconds))
    if total < 60:
        return f"{total}s"
    minutes, rem = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {rem:02d}s"
    hours, rem_minutes = divmod(minutes, 60)
    return f"{hours}h {rem_minutes:02d}m"
