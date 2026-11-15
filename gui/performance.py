"""Passive real-time traffic counters and in-session history chart."""

from __future__ import annotations

import customtkinter as ctk

from core.models import NetworkInfo, NetworkSnapshot
from gui.common import (
    ACCENT,
    ACCENT_HOVER,
    BG,
    MUTED,
    TEXT,
    BandwidthChart,
    make_card,
    make_metric_card,
    make_page_header,
)
from utils.helpers import format_bytes, format_speed


class PerformancePage(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.window_samples = 60
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.content = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)

        header = make_page_header(
            self.content,
            "Performance monitoring",
            "Observed download and upload activity from system network counters; no test traffic is generated.",
        )
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 15))

        metrics = ctk.CTkFrame(self.content, fg_color="transparent")
        metrics.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 14))
        for column in range(4):
            metrics.grid_columnconfigure(column, weight=1, uniform="traffic-metrics")
        self.download_card, self.download_value, self.download_note = make_metric_card(
            metrics, "Current download", "—", ""
        )
        self.download_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.upload_card, self.upload_value, self.upload_note = make_metric_card(
            metrics, "Current upload", "—", ""
        )
        self.upload_card.grid(row=0, column=1, sticky="nsew", padx=8)
        self.received_card, self.received_value, self.received_note = make_metric_card(
            metrics, "Received since counters started", "—", ""
        )
        self.received_card.grid(row=0, column=2, sticky="nsew", padx=8)
        self.sent_card, self.sent_value, self.sent_note = make_metric_card(
            metrics, "Sent since counters started", "—", ""
        )
        self.sent_card.grid(row=0, column=3, sticky="nsew", padx=(8, 0))

        chart = BandwidthChart(
            self.content,
            "Traffic history",
            "Samples collected during this application session · Mbit/s",
            height=3.45,
        )
        chart.card.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 12))
        self.chart = chart

        controls = make_card(self.content)
        controls.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 20))
        controls.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            controls,
            text="Chart window",
            text_color=TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=12)
        self.window_menu = ctk.CTkOptionMenu(
            controls,
            values=["30 samples", "60 samples", "120 samples", "180 samples"],
            command=self._on_window_changed,
            width=145,
            height=34,
            corner_radius=8,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
        )
        self.window_menu.set("60 samples")
        self.window_menu.grid(row=0, column=1, padx=8, pady=8)
        ctk.CTkButton(
            controls,
            text="Clear session history",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=ACCENT_HOVER,
            border_width=1,
            border_color=ACCENT,
            text_color=TEXT,
            command=self._clear_history,
        ).grid(row=0, column=2, padx=(8, 14), pady=8)
        self.interface_note = ctk.CTkLabel(
            controls,
            text="Rates are system-wide observed byte-counter deltas; local, VPN, or virtual adapter traffic may be included.",
            text_color=MUTED,
            font=ctk.CTkFont(size=10),
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.interface_note.grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=14, pady=(0, 12)
        )

    def _on_window_changed(self, value: str) -> None:
        try:
            self.window_samples = int(value.split()[0])
        except (ValueError, IndexError):
            self.window_samples = 60
        self.chart.set_history(self.app.history, limit=self.window_samples)

    def _clear_history(self) -> None:
        self.app.clear_history()
        self.chart.set_history(self.app.history, limit=self.window_samples)

    def on_snapshot(self, snapshot: NetworkSnapshot) -> None:
        self.download_value.configure(text=format_speed(snapshot.download_bps))
        self.upload_value.configure(text=format_speed(snapshot.upload_bps))
        self.download_note.configure(text="Measured receive rate")
        self.upload_note.configure(text="Measured send rate")
        self.received_value.configure(text=format_bytes(snapshot.total_received_bytes))
        self.sent_value.configure(text=format_bytes(snapshot.total_sent_bytes))
        self.received_note.configure(
            text="Cumulative OS counter; may reset with adapter/system"
        )
        self.sent_note.configure(
            text="Cumulative OS counter; may reset with adapter/system"
        )
        if self.app.current_page == "Performance":
            self.chart.set_history(self.app.history, limit=self.window_samples)

    def on_network_info(self, info: NetworkInfo) -> None:
        active = info.active_interface or "interface not identified"
        self.interface_note.configure(
            text=f"Active route: {active} · rates are system-wide observed counter deltas; local, VPN, or virtual adapter traffic may be included."
        )

    def refresh_theme(self) -> None:
        self.chart.set_history(self.app.history, limit=self.window_samples)
