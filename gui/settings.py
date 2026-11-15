"""Monitoring interval, target, theme, and launch preferences."""

from __future__ import annotations

import customtkinter as ctk

from core.ping_service import validate_target
from gui.common import (
    ACCENT,
    ACCENT_HOVER,
    BG,
    GREEN,
    MUTED,
    RED,
    TEXT,
    make_card,
    make_page_header,
)
from utils.config import AppConfig


class SettingsPage(ctk.CTkFrame):
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
            "Settings",
            "Adjust how often the app checks connectivity and how it presents live data.",
        )
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 15))

        card = make_card(self.content)
        card.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 14))
        card.grid_columnconfigure(1, weight=1)

        self.interval_entry = ctk.CTkEntry(card, width=180, height=38, corner_radius=8)
        self.target_entry = ctk.CTkEntry(card, width=300, height=38, corner_radius=8)
        self.theme_menu = ctk.CTkOptionMenu(
            card,
            values=["Dark", "Light", "System"],
            width=180,
            height=38,
            corner_radius=8,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
        )
        self.auto_start_switch = ctk.CTkSwitch(
            card,
            text="Start live monitoring automatically when the app opens",
            text_color=TEXT,
            progress_color=ACCENT,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
        )

        fields = (
            (
                "Monitoring interval",
                self.interval_entry,
                "Seconds between background checks (2–60).",
            ),
            (
                "Probe target",
                self.target_entry,
                "IPv4/IPv6 address or hostname used for rolling ICMP packet-loss estimates.",
            ),
            (
                "Appearance",
                self.theme_menu,
                "Choose dark, light, or follow the operating-system setting.",
            ),
        )
        for row, (label, widget, helper) in enumerate(fields):
            ctk.CTkLabel(
                card,
                text=label,
                text_color=TEXT,
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).grid(
                row=row,
                column=0,
                sticky="nw",
                padx=17,
                pady=(16 if row == 0 else 11, 4),
            )
            field_group = ctk.CTkFrame(card, fg_color="transparent")
            field_group.grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(10, 17),
                pady=(13 if row == 0 else 9, 4),
            )
            field_group.grid_columnconfigure(0, weight=1)
            widget.grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                field_group,
                text=helper,
                text_color=MUTED,
                font=ctk.CTkFont(size=10),
                anchor="w",
                justify="left",
                wraplength=720,
            ).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.auto_start_switch.grid(
            row=3, column=0, columnspan=2, sticky="w", padx=17, pady=(18, 6)
        )
        ctk.CTkLabel(
            card,
            text="Changes apply to the current monitoring session where possible. Auto-start affects the next launch.",
            text_color=MUTED,
            font=ctk.CTkFont(size=10),
            anchor="w",
            justify="left",
            wraplength=850,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=17, pady=(5, 14))

        actions = ctk.CTkFrame(self.content, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 10))
        ctk.CTkButton(
            actions,
            text="Save settings",
            width=140,
            height=38,
            corner_radius=9,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self.save,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Restore defaults",
            width=140,
            height=38,
            corner_radius=9,
            fg_color="transparent",
            hover_color=ACCENT_HOVER,
            border_width=1,
            border_color=ACCENT,
            text_color=TEXT,
            command=self.restore_defaults,
        ).pack(side="left", padx=9)
        self.message = ctk.CTkLabel(
            self.content,
            text="Settings are stored in your user configuration folder.",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.message.grid(row=3, column=0, sticky="ew", padx=26, pady=(0, 12))
        self.load_from_config(self.app.app_config)

    def load_from_config(self, config: AppConfig) -> None:
        self.interval_entry.delete(0, "end")
        self.interval_entry.insert(0, f"{config.monitor_interval_seconds:g}")
        self.target_entry.delete(0, "end")
        self.target_entry.insert(0, config.probe_target)
        self.theme_menu.set(config.theme.title())
        if config.auto_start_monitoring:
            self.auto_start_switch.select()
        else:
            self.auto_start_switch.deselect()

    def save(self) -> None:
        try:
            interval = float(self.interval_entry.get().strip())
        except ValueError:
            self.message.configure(
                text="Monitoring interval must be a number from 2 to 60 seconds.",
                text_color=RED,
            )
            return
        if not 2.0 <= interval <= 60.0:
            self.message.configure(
                text="Monitoring interval must be between 2 and 60 seconds.",
                text_color=RED,
            )
            return
        try:
            target = validate_target(self.target_entry.get())
        except ValueError as exc:
            self.message.configure(text=str(exc), text_color=RED)
            return
        theme = self.theme_menu.get().lower()
        config = AppConfig(
            monitor_interval_seconds=interval,
            probe_target=target,
            theme=theme,
            auto_start_monitoring=bool(self.auto_start_switch.get()),
        )
        try:
            path = self.app.save_settings(config)
        except OSError as exc:
            self.message.configure(
                text=f"Could not save settings: {exc}", text_color=RED
            )
            return
        self.message.configure(text=f"Settings saved to {path}", text_color=GREEN)
        self.load_from_config(config)

    def restore_defaults(self) -> None:
        from utils.config import DEFAULT_CONFIG

        self.load_from_config(DEFAULT_CONFIG)
        self.message.configure(
            text="Defaults loaded. Select Save settings to apply them.",
            text_color=MUTED,
        )
