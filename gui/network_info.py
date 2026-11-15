"""Network interfaces and address information page."""

from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

from core.models import NetworkInfo
from core.network_info_service import get_network_info
from gui.common import (
    ACCENT,
    BG,
    GREEN,
    MUTED,
    PANEL_ALT,
    RED,
    TEXT,
    make_card,
    make_page_header,
)
from utils.helpers import format_timestamp


class NetworkInfoPage(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self._refreshing = False
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.content = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)

        header = make_page_header(
            self.content,
            "Network information",
            "Addresses and interfaces reported by the operating system.",
        )
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 14))
        self.refresh_button = ctk.CTkButton(
            header,
            text="Refresh",
            width=100,
            height=34,
            corner_radius=9,
            fg_color=ACCENT,
            command=self.refresh,
        )
        self.refresh_button.grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 0))

        self.progress = ctk.CTkProgressBar(
            self.content, mode="indeterminate", height=5, progress_color=ACCENT
        )
        self.progress.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        self.progress.set(0)

        tile_area = ctk.CTkFrame(self.content, fg_color="transparent")
        tile_area.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 14))
        for column in range(3):
            tile_area.grid_columnconfigure(column, weight=1, uniform="network-info")
        self._tiles: dict[str, tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        tile_specs = (
            ("local_ip", "Local IPv4 address", "—"),
            ("public_ip", "Public IP address", "Not checked"),
            ("gateway", "Default gateway", "—"),
            ("hostname", "Hostname", "—"),
            ("connection_type", "Connection type", "—"),
            ("active_interface", "Active interface", "—"),
            ("dns", "DNS servers", "—"),
        )
        for index, (key, title, initial) in enumerate(tile_specs):
            row, column = divmod(index, 3)
            tile = make_card(tile_area)
            tile.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 7, 7 if column < 2 else 0),
                pady=6,
            )
            tile.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                tile,
                text=title.upper(),
                text_color=MUTED,
                font=ctk.CTkFont(size=10, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
            value_label = ctk.CTkLabel(
                tile,
                text=initial,
                text_color=TEXT,
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
                justify="left",
                wraplength=300,
            )
            value_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(3, 3))
            note_label = ctk.CTkLabel(
                tile,
                text="",
                text_color=MUTED,
                font=ctk.CTkFont(size=10),
                anchor="w",
                justify="left",
                wraplength=300,
            )
            note_label.grid(row=2, column=0, sticky="ew", padx=14, pady=(1, 12))
            self._tiles[key] = (value_label, note_label)

        interface_card = make_card(self.content)
        interface_card.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 9))
        interface_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            interface_card,
            text="Network interfaces",
            text_color=TEXT,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(15, 2))
        ctk.CTkLabel(
            interface_card,
            text="Interface status and addresses are read from psutil; inactive and virtual adapters may also appear.",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
            anchor="w",
            justify="left",
            wraplength=1000,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.interface_table = ctk.CTkFrame(interface_card, fg_color="transparent")
        self.interface_table.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 12))
        self.status_label = ctk.CTkLabel(
            self.content,
            text="Refresh to read current system information.",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.status_label.grid(row=4, column=0, sticky="ew", padx=26, pady=(0, 12))

    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        self.refresh_button.configure(state="disabled")
        self.status_label.configure(
            text="Reading interfaces and public IP…", text_color=MUTED
        )
        self.progress.start()
        self.app.run_async(
            lambda: get_network_info(include_public=True), self._on_refresh
        )

    def _on_refresh(self, result: NetworkInfo | None, error: Exception | None) -> None:
        self._refreshing = False
        self.progress.stop()
        self.refresh_button.configure(state="normal")
        if error is not None or result is None:
            message = f"Could not read network information: {error or 'unknown error'}"
            self.status_label.configure(text=message, text_color=RED)
            return
        self.app.publish_network_info(result)
        self.status_label.configure(
            text=f"Updated {format_timestamp(datetime.now().astimezone())} · public IP lookup uses api.ipify.org",
            text_color=MUTED,
        )

    def on_network_info(self, info: NetworkInfo) -> None:
        self._tiles["local_ip"][0].configure(text=info.local_ip or "Unavailable")
        self._tiles["public_ip"][0].configure(text=info.public_ip or "Unavailable")
        self._tiles["public_ip"][1].configure(
            text=info.public_ip_error or "External address reported by ipify"
        )
        self._tiles["gateway"][0].configure(text=info.gateway or "Unavailable")
        self._tiles["hostname"][0].configure(text=info.hostname or "Unknown")
        self._tiles["connection_type"][0].configure(
            text=info.connection_type or "Unknown"
        )
        self._tiles["active_interface"][0].configure(
            text=info.active_interface or "Not identified"
        )
        self._tiles["dns"][0].configure(
            text=", ".join(info.dns_servers) if info.dns_servers else "Not reported"
        )
        self._tiles["dns"][1].configure(
            text="The OS may list a local DNS stub (for example, 127.0.0.53)."
            if info.dns_servers
            else "No DNS server information was found."
        )
        self._render_interfaces(info)

    def _render_interfaces(self, info: NetworkInfo) -> None:
        for child in self.interface_table.winfo_children():
            child.destroy()
        columns = ("Interface", "State", "IPv4", "IPv6", "MAC", "Link")
        weights = (2, 1, 2, 2, 2, 1)
        for column, (heading, weight) in enumerate(zip(columns, weights)):
            self.interface_table.grid_columnconfigure(
                column, weight=weight, uniform="interfaces"
            )
            ctk.CTkLabel(
                self.interface_table,
                text=heading.upper(),
                text_color=MUTED,
                font=ctk.CTkFont(size=9, weight="bold"),
                anchor="w",
            ).grid(row=0, column=column, sticky="ew", padx=8, pady=(5, 8))

        if not info.interfaces:
            ctk.CTkLabel(
                self.interface_table,
                text="No network interfaces were reported.",
                text_color=MUTED,
                anchor="w",
            ).grid(
                row=1, column=0, columnspan=len(columns), sticky="ew", padx=8, pady=10
            )
            return

        for row, interface in enumerate(info.interfaces, start=1):
            if row % 2 == 0:
                background = PANEL_ALT
            else:
                background = "transparent"
            values = (
                interface.name,
                "Up" if interface.is_up else "Down",
                ", ".join(interface.ipv4_addresses) or "—",
                ", ".join(interface.ipv6_addresses[:2]) or "—",
                interface.mac_address or "—",
                f"{interface.speed_mbps} Mbps" if interface.speed_mbps else "—",
            )
            for column, value in enumerate(values):
                if background != "transparent":
                    cell = ctk.CTkFrame(
                        self.interface_table, fg_color=background, corner_radius=0
                    )
                    cell.grid(row=row, column=column, sticky="nsew", padx=1, pady=1)
                    cell.grid_columnconfigure(0, weight=1)
                    label_parent = cell
                    padx = 8
                else:
                    label_parent = self.interface_table
                    padx = 8
                color = (
                    GREEN
                    if column == 1 and interface.is_up
                    else (RED if column == 1 else TEXT)
                )
                ctk.CTkLabel(
                    label_parent,
                    text=value,
                    text_color=color,
                    font=ctk.CTkFont(
                        size=10, weight="bold" if column in (0, 1) else "normal"
                    ),
                    anchor="w",
                    justify="left",
                    wraplength=185,
                ).grid(
                    row=0 if background != "transparent" else row,
                    column=0 if background != "transparent" else column,
                    sticky="ew",
                    padx=padx,
                    pady=7,
                )
