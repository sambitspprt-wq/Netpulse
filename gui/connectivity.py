"""Custom ping and destination reachability page."""

from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

from core.models import PingResult
from core.ping_service import ping_host, validate_target
from gui.common import (
    ACCENT,
    ACCENT_HOVER,
    AMBER,
    BG,
    GREEN,
    MUTED,
    RED,
    TEXT,
    make_card,
    make_metric_card,
    make_page_header,
)
from utils.helpers import format_latency, format_loss, format_timestamp


class ConnectivityPage(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self._ping_inflight = False
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.content = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)

        header = make_page_header(
            self.content,
            "Ping & connectivity",
            "Send real ICMP echo requests to an IP address or hostname.",
        )
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 15))

        form = make_card(self.content)
        form.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 13))
        form.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            form,
            text="Target host",
            text_color=TEXT,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=17, pady=(15, 5))
        controls = ctk.CTkFrame(form, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=17, pady=(0, 11))
        controls.grid_columnconfigure(0, weight=1)
        self.target_entry = ctk.CTkEntry(
            controls,
            height=40,
            placeholder_text="e.g. 1.1.1.1 or example.com",
            corner_radius=9,
        )
        self.target_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.target_entry.insert(0, self.app.app_config.probe_target)
        self.count_var = ctk.StringVar(value="4")
        self.count_menu = ctk.CTkOptionMenu(
            controls,
            values=["4", "8", "12"],
            variable=self.count_var,
            width=105,
            height=40,
            corner_radius=9,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
        )
        self.count_menu.grid(row=0, column=1, padx=(0, 10))
        self.run_button = ctk.CTkButton(
            controls,
            text="Run ping",
            width=125,
            height=40,
            corner_radius=9,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self.run_ping,
        )
        self.run_button.grid(row=0, column=2)

        quick = ctk.CTkFrame(form, fg_color="transparent")
        quick.grid(row=2, column=0, sticky="ew", padx=17, pady=(0, 12))
        ctk.CTkLabel(
            quick,
            text="Quick destinations",
            text_color=MUTED,
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).pack(side="left", padx=(0, 10))
        for label, target in (
            ("Cloudflare DNS · 1.1.1.1", "1.1.1.1"),
            ("Google DNS · 8.8.8.8", "8.8.8.8"),
            ("Example domain", "example.com"),
        ):
            ctk.CTkButton(
                quick,
                text=label,
                height=29,
                corner_radius=8,
                fg_color="transparent",
                hover_color=ACCENT_HOVER,
                border_width=1,
                border_color=ACCENT,
                text_color=TEXT,
                font=ctk.CTkFont(size=10),
                command=lambda host=target: self.run_ping(host),
            ).pack(side="left", padx=(0, 7))

        self.progress = ctk.CTkProgressBar(
            self.content, mode="indeterminate", height=5, progress_color=ACCENT
        )
        self.progress.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        self.progress.set(0)

        self.results_title = ctk.CTkLabel(
            self.content,
            text="No ping test run yet",
            text_color=MUTED,
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.results_title.grid(row=3, column=0, sticky="ew", padx=25, pady=(0, 10))

        metrics = ctk.CTkFrame(self.content, fg_color="transparent")
        metrics.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 14))
        for column in range(4):
            metrics.grid_columnconfigure(column, weight=1, uniform="ping-metrics")
        self.status_card, self.status_value, self.status_note = make_metric_card(
            metrics, "Reachability", "—", ""
        )
        self.status_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.latency_card, self.latency_value, self.latency_note = make_metric_card(
            metrics, "Average RTT", "—", ""
        )
        self.latency_card.grid(row=0, column=1, sticky="nsew", padx=8)
        self.loss_card, self.loss_value, self.loss_note = make_metric_card(
            metrics, "Packet loss", "—", ""
        )
        self.loss_card.grid(row=0, column=2, sticky="nsew", padx=8)
        self.reply_card, self.reply_value, self.reply_note = make_metric_card(
            metrics, "Replies", "—", ""
        )
        self.reply_card.grid(row=0, column=3, sticky="nsew", padx=(8, 0))

        result_card = make_card(self.content)
        result_card.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 22))
        result_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            result_card,
            text="Test details",
            text_color=TEXT,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        self.output = ctk.CTkTextbox(
            result_card, height=210, wrap="word", corner_radius=9
        )
        self.output.grid(row=1, column=0, sticky="ew", padx=14, pady=(3, 14))
        self.output.insert(
            "1.0",
            "Run a test to see measured reply times and packet loss.\n\nICMP may be blocked by a firewall, VPN, router, or destination; a missing ping reply does not by itself prove that the Internet is disconnected.",
        )
        self.output.configure(state="disabled")

    def run_ping(self, target: str | None = None) -> None:
        if self._ping_inflight:
            return
        if target is None:
            target = self.target_entry.get()
        try:
            normalized = validate_target(target)
        except ValueError as exc:
            self.results_title.configure(text=str(exc), text_color=RED)
            return

        self.target_entry.delete(0, "end")
        self.target_entry.insert(0, normalized)
        count = int(self.count_var.get())
        self._ping_inflight = True
        self.run_button.configure(state="disabled")
        self.results_title.configure(
            text=f"Pinging {normalized} · {count} probes…", text_color=MUTED
        )
        self.progress.start()
        self.app.run_async(
            lambda: ping_host(normalized, count=count, timeout_ms=1200), self._on_ping
        )

    def _on_ping(self, result: PingResult | None, error: Exception | None) -> None:
        self._ping_inflight = False
        self.progress.stop()
        self.run_button.configure(state="normal")
        if error is not None or result is None:
            message = f"Ping test failed: {error or 'unknown error'}"
            self.results_title.configure(text=message, text_color=RED)
            return

        self.results_title.configure(
            text=f"Finished {format_timestamp(datetime.now().astimezone())} · {result.target}"
            + (f" resolved to {result.resolved_ip}" if result.resolved_ip else ""),
            text_color=MUTED,
        )
        if result.received == result.sent and result.received > 0:
            status, color = "REACHABLE", GREEN
        elif result.received > 0:
            status, color = "PARTIAL", AMBER
        else:
            status, color = "NO REPLY", RED
        self.status_value.configure(text=status, text_color=color)
        self.status_note.configure(text="ICMP replies received")
        all_sub_ms = bool(result.times_display) and all(
            label.startswith("< 1") for label in result.times_display
        )
        average_text = "<1 ms" if all_sub_ms else format_latency(result.average_ms)
        self.latency_value.configure(text=average_text)
        self.latency_note.configure(
            text="All replies reported below 1 ms by the OS"
            if all_sub_ms
            else (
                f"Min {format_latency(result.min_ms)} · Max {format_latency(result.max_ms)}"
                if result.times_ms
                else "No measured RTT"
            )
        )
        self.loss_value.configure(
            text=format_loss(result.loss_percent), text_color=color
        )
        self.loss_note.configure(
            text=f"{result.sent - result.received} of {result.sent} probes lost"
        )
        self.reply_value.configure(text=f"{result.received}/{result.sent}")
        self.reply_note.configure(text="received / sent")

        lines = [
            f"Target: {result.target}",
            f"Resolved IP address: {result.resolved_ip or 'not resolved'}",
            f"Packets: {result.received} received, {result.sent} sent, {format_loss(result.loss_percent)} loss",
        ]
        if result.times_ms:
            lines.extend(
                (
                    f"Minimum RTT: {format_latency(result.min_ms)}",
                    f"Average RTT: {format_latency(result.average_ms)}",
                    f"Maximum RTT: {format_latency(result.max_ms)}",
                    "",
                    "Successful reply times:",
                )
            )
            lines.extend(
                f"  Reply {index}: {result.times_display[index - 1] if index - 1 < len(result.times_display) else format_latency(milliseconds)}"
                for index, milliseconds in enumerate(result.times_ms, start=1)
            )
        if result.error:
            lines.extend(("", result.error))
        if result.received == 0 and result.command_output:
            lines.extend(("", "System ping output:", result.command_output[-600:]))
        if (
            result.times_display
            and any(label.startswith("<") for label in result.times_display)
            and not all_sub_ms
        ):
            lines.extend(
                (
                    "",
                    "The OS reported sub-millisecond replies as upper bounds; summary statistics use those reported bounds.",
                )
            )
        lines.extend(
            (
                "",
                "RTT values are parsed from the operating system ping utility. ICMP filtering may affect results.",
            )
        )
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", "\n".join(lines))
        self.output.configure(state="disabled")
