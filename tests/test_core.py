"""Offline unit tests for core parsing, formatting, config, and sampling logic."""

from __future__ import annotations

import unittest
from collections import namedtuple
from unittest.mock import patch

from core.ping_service import extract_ping_samples, extract_ping_times, validate_target
from core.speed_monitor import SpeedMonitor
from utils.config import AppConfig, _sanitize
from utils.helpers import format_bytes, format_speed


class PingValidationTests(unittest.TestCase):
    def test_accepts_ipv4_and_hostnames(self) -> None:
        self.assertEqual(validate_target("1.1.1.1"), "1.1.1.1")
        self.assertEqual(
            validate_target("2001:4860:4860::8888"), "2001:4860:4860::8888"
        )
        self.assertEqual(validate_target("Example.COM."), "Example.COM")

    def test_rejects_shell_like_or_option_like_values(self) -> None:
        for value in ("", "-n", "example.com; whoami", "bad host", "bad..host"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_target(value)

    def test_parses_windows_and_unix_rtt_formats(self) -> None:
        lines = [
            "Reply from 1.1.1.1: bytes=32 time=12ms TTL=57",
            "Reply from 1.1.1.1: bytes=32 time<1ms TTL=57",
            "64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=0.75 ms",
            "Request timed out.",
        ]
        self.assertEqual(extract_ping_times(lines), (12.0, 1.0, 0.75))
        numeric, labels = extract_ping_samples(lines)
        self.assertEqual(numeric, (12.0, 1.0, 0.75))
        self.assertEqual(labels, ("12 ms", "< 1 ms", "0.75 ms"))


class SpeedMonitorTests(unittest.TestCase):
    def test_rate_uses_counter_delta_over_elapsed_time(self) -> None:
        Counters = namedtuple("Counters", "bytes_recv bytes_sent")
        monitor = SpeedMonitor()
        with patch(
            "core.speed_monitor.psutil.net_io_counters",
            side_effect=[Counters(1000, 500), Counters(3000, 900)],
        ):
            with patch("core.speed_monitor.time.monotonic", side_effect=[10.0, 12.0]):
                first = monitor.sample()
                second = monitor.sample()
        self.assertIsNone(first.download_bps)
        self.assertEqual(second.download_bps, 1000.0)
        self.assertEqual(second.upload_bps, 200.0)
        self.assertEqual(second.total_received_bytes, 3000)
        self.assertEqual(second.total_sent_bytes, 900)

    def test_counter_reset_does_not_report_negative_rate(self) -> None:
        Counters = namedtuple("Counters", "bytes_recv bytes_sent")
        monitor = SpeedMonitor()
        with patch(
            "core.speed_monitor.psutil.net_io_counters",
            side_effect=[Counters(200, 300), Counters(100, 250)],
        ):
            with patch("core.speed_monitor.time.monotonic", side_effect=[1.0, 2.0]):
                monitor.sample()
                second = monitor.sample()
        self.assertIsNone(second.download_bps)
        self.assertIsNone(second.upload_bps)


class ConfigAndFormattingTests(unittest.TestCase):
    def test_config_bounds_and_fallbacks(self) -> None:
        config = _sanitize(
            {
                "monitor_interval_seconds": 1000,
                "probe_target": "-n",
                "theme": "neon",
                "auto_start_monitoring": "yes",
            }
        )
        self.assertEqual(config.monitor_interval_seconds, 60.0)
        self.assertEqual(config.probe_target, AppConfig().probe_target)
        self.assertEqual(config.theme, "dark")
        self.assertTrue(config.auto_start_monitoring)

    def test_formatting(self) -> None:
        self.assertEqual(format_speed(None), "—")
        self.assertEqual(format_speed(125_000), "1.00 Mbps")
        self.assertEqual(format_bytes(1024), "1.00 KB")


if __name__ == "__main__":
    unittest.main()
