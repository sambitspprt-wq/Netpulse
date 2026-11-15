"""Live overview page."""

from __future__ import annotations

import customtkinter as ctk

from core.models import NetworkInfo, NetworkSnapshot
from gui.common import (
    ACCENT,
    BG,
    GREEN,
    MUTED,
    RED,
    TEXT,
    BandwidthChart,
    add_info_row,
    make_card,
    make_metric_card,
    make_page_header,
)
from utils.helpers import (
    format_duration,
    format_latency,
    format_loss,
    format_speed,
    format_timestamp,
)


class DashboardPage(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.content = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)

        header = make_page_header(
            self.content,
            "Network overview",
            "Live connectivity and observed traffic from this computer.",
        )
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 17))
        ctk.CTkButton(
            header,
            text="Refresh network info",
            width=155,
            height=34,
            corner_radius=9,
            fg_color=ACCENT,
            hover_color=ACCENT,
            command=self.app.refresh_network_info,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 0))

        cards = ctk.CTkFrame(self.content, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 14))
        for column in range(4):
            cards.grid_columnconfigure(column, weight=1, uniform="metrics")

        self.status_card, self.status_value, self.status_caption = make_metric_card(
            cards,
            "Internet status",
            "WAITING",
            "Waiting for the first connectivity check",
        )
        self.status_card.grid(row=0, column=0, sticky="nsew", padx=(0, 9), pady=2)
        self.latency_card, self.latency_value, self.latency_caption = make_metric_card(
            cards, "Internet latency", "—", "HTTPS / TCP reachability check"
        )
        self.latency_card.grid(row=0, column=1, sticky="nsew", padx=9, pady=2)
        self.download_card, self.download_value, self.download_caption = (
            make_metric_card(cards, "Download", "—", "Observed system traffic")
        )
        self.download_card.grid(row=0, column=2, sticky="nsew", padx=9, pady=2)
        self.upload_card, self.upload_value, self.upload_caption = make_metric_card(
            cards, "Upload", "—", "Observed system traffic"
        )
        self.upload_card.grid(row=0, column=3, sticky="nsew", padx=(9, 0), pady=2)

        lower = ctk.CTkFrame(self.content, fg_color="transparent")
        lower.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        lower.grid_columnconfigure(0, weight=3)
        lower.grid_columnconfigure(1, weight=1)
        lower.grid_rowconfigure(0, weight=1)

        self.chart = BandwidthChart(
            lower,
            "Live bandwidth",
            "Measured interface-counter rates · Mbit/s",
            height=2.75,
        )
        self.chart.card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.details_card = make_card(lower)
        self.details_card.grid(row=0, column=1, sticky="nsew")
        self.details_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self.details_card,
            text="Connection details",
            text_color=TEXT,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=15, pady=(15, 9))
        self.local_ip_value = add_info_row(self.details_card, "Local IP", "—", row=1)
        self.gateway_value = add_info_row(
            self.details_card, "Default gateway", "—", row=2
        )
        self.connection_type_value = add_info_row(
            self.details_card, "Connection", "—", row=3
        )
        self.packet_loss_value = add_info_row(
            self.details_card, "Probe packet loss", "—", row=4
        )
        self.probe_rtt_value = add_info_row(self.details_card, "Probe RTT", "—", row=5)
        self.probe_target_value = add_info_row(
            self.details_card, "Probe target", "1.1.1.1", row=6
        )
        self.outage_value = add_info_row(
            self.details_card, "Outages this session", "0", row=7
        )
        self.last_outage_value = add_info_row(
            self.details_card, "Last interruption", "—", row=8
        )
        ctk.CTkLabel(
            self.details_card,
            text="Packet loss is estimated from rolling ICMP probes; routers may filter ping.",
            text_color=MUTED,
            font=ctk.CTkFont(size=10),
            wraplength=260,
            justify="left",
        ).grid(row=9, column=0, columnspan=2, sticky="ew", padx=15, pady=(9, 14))

        self._latest_snapshot: NetworkSnapshot | None = None

    def on_snapshot(self, snapshot: NetworkSnapshot) -> None:
        self._latest_snapshot = snapshot
        status = "CONNECTED" if snapshot.internet_connected else "DISCONNECTED"
        color = GREEN if snapshot.internet_connected else RED
        self.status_value.configure(text=status, text_color=color)
        if snapshot.internet_connected:
            self.status_caption.configure(
                text=f"Verified via {snapshot.internet_method}"
            )
        else:
            self.status_caption.configure(
                text=snapshot.internet_error or "Internet check did not succeed"
            )

        self.latency_value.configure(text=format_latency(snapshot.internet_latency_ms))
        self.latency_caption.configure(
            text=f"Last checked {format_timestamp(snapshot.timestamp)} · {snapshot.internet_method}"
        )
        self.download_value.configure(text=format_speed(snapshot.download_bps))
        self.upload_value.configure(text=format_speed(snapshot.upload_bps))
        self.download_caption.configure(text="Current measured receive rate")
        self.upload_caption.configure(text="Current measured send rate")

        self.packet_loss_value.configure(text=format_loss(snapshot.packet_loss_percent))
        self.probe_rtt_value.configure(text=format_latency(snapshot.ping_latency_ms))
        self.probe_target_value.configure(text=snapshot.probe_target)
        self.outage_value.configure(text=str(snapshot.outage_count))
        if (
            not snapshot.internet_connected
            and snapshot.last_outage_duration_seconds is not None
        ):
            self.last_outage_value.configure(
                text=f"Offline {format_duration(snapshot.last_outage_duration_seconds)}"
            )
        elif snapshot.last_interruption:
            duration = format_duration(snapshot.last_outage_duration_seconds)
            self.last_outage_value.configure(
                text=f"{format_timestamp(snapshot.last_interruption)} ({duration})"
            )
        else:
            self.last_outage_value.configure(text="None detected")

        if self.app.current_page == "Dashboard":
            self.chart.set_history(self.app.history, limit=45)

    def on_network_info(self, info: NetworkInfo) -> None:
        self.local_ip_value.configure(text=info.local_ip or "Unavailable")
        self.gateway_value.configure(text=info.gateway or "Unavailable")
        self.connection_type_value.configure(text=info.connection_type)

    def refresh_theme(self) -> None:
        self.chart.set_history(self.app.history, limit=45)
