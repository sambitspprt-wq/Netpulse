"""On-demand adapter, gateway, DNS, and Internet diagnosis page."""

from __future__ import annotations

import customtkinter as ctk

from core.diagnostics import diagnose_network
from core.models import DiagnosticReport
from gui.common import (
    ACCENT,
    BG,
    MUTED,
    RED,
    TEXT,
    make_card,
    make_page_header,
    status_palette,
)
from utils.helpers import format_timestamp


class TroubleshootingPage(ctk.CTkFrame):
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
            "Troubleshooting",
            "Run checks for the local adapter, default gateway, DNS resolution, and Internet reachability.",
        )
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 14))
        self.run_button = ctk.CTkButton(
            header,
            text="Run diagnosis",
            width=140,
            height=36,
            corner_radius=9,
            fg_color=ACCENT,
            command=self.run_diagnosis,
        )
        self.run_button.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

        note = make_card(self.content)
        note.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        ctk.CTkLabel(
            note,
            text="How to read these results",
            text_color=TEXT,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            note,
            text="A gateway ping can be blocked even when the network works. Internet status is checked separately over HTTPS/TCP; DNS uses the system resolver. Recommendations are general guidance, not automatic configuration changes.",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
            anchor="w",
            justify="left",
            wraplength=1050,
        ).pack(anchor="w", padx=14, pady=(0, 12))

        self.progress = ctk.CTkProgressBar(
            self.content, mode="indeterminate", height=5, progress_color=ACCENT
        )
        self.progress.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 11))
        self.progress.set(0)
        self.summary_card = make_card(self.content)
        self.summary_card.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
        self.summary_label = ctk.CTkLabel(
            self.summary_card,
            text="Run a diagnosis to see measured results.",
            text_color=MUTED,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=1050,
        )
        self.summary_label.pack(anchor="w", padx=16, pady=15)

        self.checks_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.checks_frame.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 10))
        self.checks_frame.grid_columnconfigure(0, weight=1)
        self.recommendations_card = make_card(self.content)
        self.recommendations_card.grid(
            row=5, column=0, sticky="ew", padx=24, pady=(0, 24)
        )
        self.recommendations_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.recommendations_card,
            text="Suggested next steps",
            text_color=TEXT,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        self.recommendation_body = ctk.CTkLabel(
            self.recommendations_card,
            text="Suggestions will appear after the checks complete.",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
            anchor="w",
            justify="left",
            wraplength=1000,
        )
        self.recommendation_body.grid(
            row=1, column=0, sticky="ew", padx=16, pady=(3, 14)
        )

    def run_diagnosis(self) -> None:
        self.run_button.configure(state="disabled")
        self.summary_label.configure(
            text="Running adapter, gateway, DNS, and Internet checks…", text_color=MUTED
        )
        self.recommendation_body.configure(
            text="Please wait for the live checks to finish."
        )
        for child in self.checks_frame.winfo_children():
            child.destroy()
        self.progress.start()
        self.app.run_async(diagnose_network, self._on_diagnosis)

    def _on_diagnosis(
        self, report: DiagnosticReport | None, error: Exception | None
    ) -> None:
        self.progress.stop()
        self.run_button.configure(state="normal")
        if error is not None or report is None:
            self.summary_label.configure(
                text=f"Diagnosis failed: {error or 'unknown error'}", text_color=RED
            )
            return
        self.summary_label.configure(
            text=f"{report.summary}\nCompleted {format_timestamp(report.generated_at)}",
            text_color=TEXT,
        )
        for row, check in enumerate(report.checks):
            color = status_palette(check.status)
            card = make_card(self.checks_frame)
            card.grid(row=row, column=0, sticky="ew", pady=5)
            card.grid_columnconfigure(1, weight=1)
            status = ctk.CTkLabel(
                card,
                text=check.status,
                text_color=color,
                font=ctk.CTkFont(size=10, weight="bold"),
                width=64,
                anchor="w",
            )
            status.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(14, 12), pady=13)
            ctk.CTkLabel(
                card,
                text=check.label,
                text_color=TEXT,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            ).grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(11, 1))
            detail = check.detail
            if check.recommendation:
                detail += f"\nSuggestion: {check.recommendation}"
            ctk.CTkLabel(
                card,
                text=detail,
                text_color=MUTED,
                font=ctk.CTkFont(size=11),
                anchor="w",
                justify="left",
                wraplength=1000,
            ).grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(1, 11))

        recommendations = "\n".join(f"• {item}" for item in report.recommendations)
        self.recommendation_body.configure(text=recommendations)
