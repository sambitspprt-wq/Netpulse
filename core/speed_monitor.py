"""Passive network throughput measurement from psutil interface counters."""

from __future__ import annotations

import time
from typing import Optional

import psutil

from core.models import TrafficSample


class SpeedMonitor:
    """Calculate observed system-wide RX/TX rates without generating traffic."""

    def __init__(self) -> None:
        self._previous_time: Optional[float] = None
        self._previous_received: Optional[int] = None
        self._previous_sent: Optional[int] = None

    def sample(self) -> TrafficSample:
        now = time.monotonic()
        try:
            counters = psutil.net_io_counters()
        except (OSError, RuntimeError):
            counters = None

        if counters is None:
            self._previous_time = now
            self._previous_received = None
            self._previous_sent = None
            return TrafficSample(None, None, None, None)

        total_received = int(counters.bytes_recv)
        total_sent = int(counters.bytes_sent)
        download_bps: Optional[float] = None
        upload_bps: Optional[float] = None

        if (
            self._previous_time is not None
            and self._previous_received is not None
            and self._previous_sent is not None
        ):
            elapsed = now - self._previous_time
            received_delta = total_received - self._previous_received
            sent_delta = total_sent - self._previous_sent
            if elapsed > 0 and received_delta >= 0 and sent_delta >= 0:
                download_bps = received_delta / elapsed
                upload_bps = sent_delta / elapsed

        self._previous_time = now
        self._previous_received = total_received
        self._previous_sent = total_sent
        return TrafficSample(download_bps, upload_bps, total_received, total_sent)

    def reset(self) -> None:
        """Forget the previous counter sample; next rate will be unavailable."""
        self._previous_time = None
        self._previous_received = None
        self._previous_sent = None
