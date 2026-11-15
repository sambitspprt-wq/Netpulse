"""Shared palette, dashboard widgets, and embedded throughput chart."""

from __future__ import annotations

import math
from typing import Iterable, Optional

import customtkinter as ctk
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from core.models import NetworkSnapshot

# CustomTkinter resolves light/dark tuples automatically for native widgets.
BG = ("#F3F6FB", "#0A1220")
SIDEBAR = ("#FFFFFF", "#0D1728")
PANEL = ("#FFFFFF", "#111D30")
PANEL_ALT = ("#F5F8FC", "#18263B")
BORDER = ("#DCE5F0", "#253650")
TEXT = ("#17263C", "#E8EFF8")
MUTED = ("#64748B", "#96A9C2")
ACCENT = ("#2563EB", "#4D8EFF")
ACCENT_HOVER = ("#1D4ED8", "#3779E8")
GREEN = ("#14805E", "#34D399")
RED = ("#C2413B", "#FB7185")
AMBER = ("#A16207", "#FBBF24")
PURPLE = ("#6D4AD1", "#A78BFA")


def resolve_color(color: object) -> str:
    """Resolve a CustomTkinter light/dark color tuple for Matplotlib/Tk canvas."""
    if isinstance(color, (tuple, list)) and len(color) == 2:
        mode = ctk.get_appearance_mode().lower()
        return str(color[1] if mode == "dark" else color[0])
    return str(color)


def make_card(parent, *, corner_radius: int = 16):
    return ctk.CTkFrame(
        parent,
        fg_color=PANEL,
        corner_radius=corner_radius,
        border_width=1,
        border_color=BORDER,
    )


def make_page_header(parent, title: str, subtitle: str):
    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.grid_columnconfigure(0, weight=1)
    title_label = ctk.CTkLabel(
        header,
        text=title,
        text_color=TEXT,
        font=ctk.CTkFont(size=25, weight="bold"),
        anchor="w",
    )
    title_label.grid(row=0, column=0, sticky="w")
    subtitle_label = ctk.CTkLabel(
        header,
        text=subtitle,
        text_color=MUTED,
        font=ctk.CTkFont(size=13),
        anchor="w",
        justify="left",
    )
    subtitle_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
    return header


def make_metric_card(parent, title: str, value: str = "—", subtitle: str = ""):
    card = make_card(parent)
    card.grid_columnconfigure(0, weight=1)
    title_label = ctk.CTkLabel(
        card,
        text=title.upper(),
        text_color=MUTED,
        font=ctk.CTkFont(size=10, weight="bold"),
        anchor="w",
    )
    title_label.grid(row=0, column=0, sticky="ew", padx=15, pady=(14, 2))
    value_label = ctk.CTkLabel(
        card,
        text=value,
        text_color=TEXT,
        font=ctk.CTkFont(size=24, weight="bold"),
        anchor="w",
    )
    value_label.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 0))
    subtitle_label = ctk.CTkLabel(
        card,
        text=subtitle,
        text_color=MUTED,
        font=ctk.CTkFont(size=11),
        anchor="w",
        justify="left",
    )
    subtitle_label.grid(row=2, column=0, sticky="ew", padx=15, pady=(2, 13))
    return card, value_label, subtitle_label


def add_info_row(parent, label: str, value: str = "—", *, row: int, value_color=TEXT):
    label_widget = ctk.CTkLabel(
        parent,
        text=label,
        text_color=MUTED,
        font=ctk.CTkFont(size=11),
        anchor="w",
    )
    label_widget.grid(row=row, column=0, sticky="w", padx=(15, 10), pady=5)
    value_widget = ctk.CTkLabel(
        parent,
        text=value,
        text_color=value_color,
        font=ctk.CTkFont(size=12, weight="bold"),
        anchor="e",
        justify="right",
    )
    value_widget.grid(row=row, column=1, sticky="ew", padx=(4, 15), pady=5)
    return value_widget


def status_palette(status: str):
    normalized = status.upper()
    if normalized in {"PASS", "CONNECTED", "ONLINE", "OK"}:
        return GREEN
    if normalized in {"WARN", "WARNING", "PARTIAL"}:
        return AMBER
    if normalized in {"FAIL", "DISCONNECTED", "OFFLINE", "ERROR"}:
        return RED
    return MUTED


class BandwidthChart:
    """An embedded Matplotlib chart driven only by collected psutil samples."""

    def __init__(self, parent, title: str, subtitle: str = "", *, height: float = 2.65):
        self.card = make_card(parent)
        self.card.grid_columnconfigure(0, weight=1)
        self.card.grid_rowconfigure(1, weight=1)

        title_area = ctk.CTkFrame(self.card, fg_color="transparent")
        title_area.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 2))
        title_area.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            title_area,
            text=title,
            text_color=TEXT,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        if subtitle:
            ctk.CTkLabel(
                title_area,
                text=subtitle,
                text_color=MUTED,
                font=ctk.CTkFont(size=11),
                anchor="e",
            ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.figure = Figure(figsize=(8.2, height), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.card)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(highlightthickness=0, bd=0)
        self.canvas_widget.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.set_history(())

    def set_history(
        self, history: Iterable[NetworkSnapshot], limit: Optional[int] = None
    ) -> None:
        samples = list(history)
        if limit is not None:
            samples = samples[-max(1, int(limit)) :]
        measured = [
            sample
            for sample in samples
            if sample.download_bps is not None or sample.upload_bps is not None
        ]

        background = resolve_color(PANEL)
        border = resolve_color(BORDER)
        muted = resolve_color(MUTED)
        text = resolve_color(TEXT)
        blue = resolve_color(ACCENT)
        green = resolve_color(GREEN)
        self.figure.set_facecolor(background)
        self.axes.clear()
        self.axes.set_facecolor(background)
        self.canvas_widget.configure(bg=background)

        if not measured:
            self.axes.text(
                0.5,
                0.5,
                "Collecting real network samples…",
                ha="center",
                va="center",
                color=muted,
                transform=self.axes.transAxes,
                fontsize=10,
            )
            self.axes.set_xticks([])
            self.axes.set_yticks([])
        else:
            timestamps = [sample.timestamp for sample in measured]
            download = [
                (sample.download_bps * 8.0 / 1_000_000.0)
                if sample.download_bps is not None
                else math.nan
                for sample in measured
            ]
            upload = [
                (sample.upload_bps * 8.0 / 1_000_000.0)
                if sample.upload_bps is not None
                else math.nan
                for sample in measured
            ]
            marker = "o" if len(measured) == 1 else None
            self.axes.plot(
                timestamps,
                download,
                color=blue,
                linewidth=2.0,
                marker=marker,
                markersize=4,
                label="Download",
            )
            self.axes.plot(
                timestamps,
                upload,
                color=green,
                linewidth=2.0,
                marker=marker,
                markersize=4,
                label="Upload",
            )
            max_rate = max(
                (value for value in download + upload if math.isfinite(value)),
                default=0.0,
            )
            self.axes.set_ylim(bottom=0, top=max(0.1, max_rate * 1.2))
            self.axes.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            self.axes.yaxis.set_major_formatter(
                FuncFormatter(lambda value, _position: f"{value:g}")
            )
            self.axes.set_ylabel("Mbit/s", color=muted, fontsize=9)
            self.axes.tick_params(axis="x", colors=muted, labelsize=8, rotation=0)
            self.axes.tick_params(axis="y", colors=muted, labelsize=8)
            self.axes.grid(True, axis="y", color=border, linewidth=0.7, alpha=0.8)
            self.axes.grid(True, axis="x", color=border, linewidth=0.45, alpha=0.45)
            for spine in self.axes.spines.values():
                spine.set_color(border)
            legend = self.axes.legend(
                loc="upper left", frameon=False, ncols=2, fontsize=8
            )
            for label in legend.get_texts():
                label.set_color(text)
        self.figure.tight_layout(pad=1.3)
        self.canvas.draw_idle()
