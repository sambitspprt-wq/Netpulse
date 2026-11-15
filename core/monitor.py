"""Background network monitor that emits immutable snapshots to the GUI."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Optional

from core.connectivity_service import check_internet
from core.models import ConnectivityCheck, NetworkSnapshot, PingResult, TrafficSample
from core.ping_service import ping_host
from core.speed_monitor import SpeedMonitor

logger = logging.getLogger(__name__)
SnapshotCallback = Callable[[NetworkSnapshot], None]


class NetworkMonitor:
    """Run real connectivity, ping, and interface-counter samples off the UI thread."""

    def __init__(
        self, interval_seconds: float = 3.0, probe_target: str = "1.1.1.1"
    ) -> None:
        self._interval_seconds = self._valid_interval(interval_seconds)
        self._probe_target = probe_target
        self._settings_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[SnapshotCallback] = None

    @staticmethod
    def _valid_interval(value: float) -> float:
        return max(2.0, min(float(value), 60.0))

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def update_settings(self, interval_seconds: float, probe_target: str) -> None:
        with self._settings_lock:
            self._interval_seconds = self._valid_interval(interval_seconds)
            self._probe_target = probe_target
        self._wake_event.set()

    def start(self, callback: SnapshotCallback) -> bool:
        """Start sampling. Returns False if a monitor thread is already running."""
        if self.is_running:
            return False
        self._callback = callback
        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="network-monitor", daemon=True
        )
        self._thread.start()
        return True

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, timeout))

    def _read_settings(self) -> tuple[float, str]:
        with self._settings_lock:
            return self._interval_seconds, self._probe_target

    @staticmethod
    def _safe_internet_check(timeout: float) -> ConnectivityCheck:
        try:
            return check_internet(timeout=timeout)
        except Exception as exc:  # keep a transient service error from killing sampling
            logger.exception("Internet check failed unexpectedly")
            return ConnectivityCheck(False, None, "Unavailable", str(exc))

    @staticmethod
    def _safe_ping(target: str) -> PingResult:
        try:
            return ping_host(target, count=1, timeout_ms=1000)
        except Exception as exc:
            logger.exception("Monitor ping failed unexpectedly")
            return PingResult(target, None, 1, 0, loss_percent=100.0, error=str(exc))

    @staticmethod
    def _safe_traffic(sampler: SpeedMonitor) -> TrafficSample:
        try:
            return sampler.sample()
        except Exception:
            logger.exception("Could not sample network byte counters")
            return TrafficSample(None, None, None, None)

    def _run(self) -> None:
        sampler = SpeedMonitor()
        probe_history: deque[bool] = deque(maxlen=20)
        previous_connected: Optional[bool] = None
        disconnected_since: Optional[datetime] = None
        outage_count = 0
        last_interruption: Optional[datetime] = None
        last_outage_duration: Optional[float] = None

        while not self._stop_event.is_set():
            cycle_started = time.monotonic()
            interval, target = self._read_settings()
            traffic = self._safe_traffic(sampler)
            internet = self._safe_internet_check(
                timeout=min(2.5, max(1.0, interval * 0.75))
            )
            probe = self._safe_ping(target)
            probe_history.append(probe.received > 0)
            now = datetime.now().astimezone()

            if previous_connected is None:
                if not internet.connected:
                    disconnected_since = now
            elif previous_connected and not internet.connected:
                outage_count += 1
                disconnected_since = now
            elif not previous_connected and internet.connected:
                if disconnected_since is not None:
                    last_interruption = disconnected_since
                    last_outage_duration = max(
                        0.0, (now - disconnected_since).total_seconds()
                    )
                disconnected_since = None
            previous_connected = internet.connected

            current_outage_duration = last_outage_duration
            if not internet.connected and disconnected_since is not None:
                current_outage_duration = max(
                    0.0, (now - disconnected_since).total_seconds()
                )

            loss_percent = None
            # Avoid presenting a very small early sample as a stable estimate.
            if len(probe_history) >= 5:
                loss_percent = (
                    100.0
                    * (len(probe_history) - sum(probe_history))
                    / len(probe_history)
                )

            snapshot = NetworkSnapshot(
                timestamp=now,
                internet_connected=internet.connected,
                internet_latency_ms=internet.latency_ms,
                internet_method=internet.method,
                internet_error=internet.error,
                download_bps=traffic.download_bps,
                upload_bps=traffic.upload_bps,
                total_received_bytes=traffic.total_received_bytes,
                total_sent_bytes=traffic.total_sent_bytes,
                packet_loss_percent=loss_percent,
                ping_latency_ms=probe.average_ms,
                probe_target=target,
                probe_samples=len(probe_history),
                outage_count=outage_count,
                last_interruption=last_interruption,
                last_outage_duration_seconds=current_outage_duration,
            )

            callback = self._callback
            if callback:
                try:
                    callback(snapshot)
                except Exception:
                    logger.exception("Snapshot callback failed")

            wait_seconds = max(0.0, interval - (time.monotonic() - cycle_started))
            self._wake_event.wait(wait_seconds)
            self._wake_event.clear()
