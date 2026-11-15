"""Application shell, navigation, background workers, and monitor event routing."""

from __future__ import annotations

import logging
import queue
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Optional

import customtkinter as ctk

from core.models import NetworkInfo, NetworkSnapshot
from core.monitor import NetworkMonitor
from core.network_info_service import get_network_info
from gui.common import ACCENT, ACCENT_HOVER, BG, GREEN, MUTED, RED, SIDEBAR, TEXT
from gui.connectivity import ConnectivityPage
from gui.dashboard import DashboardPage
from gui.network_info import NetworkInfoPage
from gui.performance import PerformancePage
from gui.settings import SettingsPage
from gui.troubleshooting import TroubleshootingPage
from utils.config import AppConfig, load_config, save_config

logger = logging.getLogger(__name__)


class NetworkMonitorApp(ctk.CTk):
    """Desktop UI; all network operations run outside Tk's event thread."""

    def __init__(self) -> None:
        self.app_config = load_config()
        ctk.set_appearance_mode(self.app_config.theme)
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title("Network Monitor | NetPulse")
        self.geometry("1380x880")
        self.minsize(1080, 700)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.history: deque[NetworkSnapshot] = deque(maxlen=180)
        self.latest_snapshot: Optional[NetworkSnapshot] = None
        self.latest_network_info: Optional[NetworkInfo] = None
        self.current_page = "Dashboard"
        self._closing = False
        self._monitor_requested = False
        self._info_request_inflight = False
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="network-ui-task"
        )
        self._monitor_queue: queue.Queue[NetworkSnapshot] = queue.Queue(maxsize=8)
        self.monitor = NetworkMonitor(
            interval_seconds=self.app_config.monitor_interval_seconds,
            probe_target=self.app_config.probe_target,
        )

        self._build_layout()
        self._build_pages()
        self._refresh_navigation()
        self._update_toolbar()
        self.after(150, self._poll_monitor_queue)
        self.after(400, self.refresh_network_info)
        if self.app_config.auto_start_monitoring:
            self.after(250, self.start_monitoring)

    def _build_layout(self) -> None:
        self.shell = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.shell.pack(fill="both", expand=True)
        self.shell.grid_columnconfigure(1, weight=1)
        self.shell.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self.shell, width=232, fg_color=SIDEBAR, corner_radius=0
        )
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        # Leave a flexible spacer below navigation so the footer stays at the bottom.
        self.sidebar.grid_rowconfigure(8, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(21, 26))
        logo = ctk.CTkFrame(
            brand, width=39, height=39, corner_radius=12, fg_color=ACCENT
        )
        logo.pack(side="left")
        logo.pack_propagate(False)
        ctk.CTkLabel(
            logo,
            text="N",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=21, weight="bold"),
        ).pack(expand=True)
        brand_copy = ctk.CTkFrame(brand, fg_color="transparent")
        brand_copy.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(
            brand_copy,
            text="NETPULSE",
            text_color=TEXT,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand_copy,
            text="NETWORK MONITOR",
            text_color=MUTED,
            font=ctk.CTkFont(size=9, weight="bold"),
            anchor="w",
        ).pack(anchor="w", pady=(1, 0))

        ctk.CTkLabel(
            self.sidebar,
            text="WORKSPACE",
            text_color=MUTED,
            font=ctk.CTkFont(size=9, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))

        self.navigation = (
            ("Dashboard", "Overview"),
            ("Network information", "Network information"),
            ("Ping & connectivity", "Ping & connectivity"),
            ("Performance", "Performance"),
            ("Troubleshooting", "Troubleshooting"),
            ("Settings", "Settings"),
        )
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for index, (key, label) in enumerate(self.navigation, start=2):
            button = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                height=42,
                corner_radius=10,
                fg_color="transparent",
                hover_color=ACCENT_HOVER,
                text_color=TEXT,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda page=key: self.show_page(page),
            )
            button.grid(row=index, column=0, sticky="ew", padx=12, pady=3)
            self.nav_buttons[key] = button

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=9, column=0, sticky="sew", padx=17, pady=(10, 17))
        ctk.CTkFrame(footer, height=1, fg_color=("#E6ECF4", "#24334B")).pack(
            fill="x", pady=(0, 11)
        )
        ctk.CTkLabel(
            footer,
            text="LOCAL TELEMETRY",
            text_color=MUTED,
            font=ctk.CTkFont(size=9, weight="bold"),
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            footer,
            text="Passive counters · no test load",
            text_color=MUTED,
            font=ctk.CTkFont(size=9),
            anchor="w",
        ).pack(anchor="w", pady=(3, 0))

        self.main_area = ctk.CTkFrame(self.shell, fg_color=BG, corner_radius=0)
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(1, weight=1)

        self.toolbar = ctk.CTkFrame(
            self.main_area, height=62, fg_color=SIDEBAR, corner_radius=0
        )
        self.toolbar.grid(row=0, column=0, sticky="ew")
        self.toolbar.grid_propagate(False)
        self.toolbar.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=24, pady=10)
        self.monitor_dot = ctk.CTkLabel(
            left, text="●", text_color=MUTED, font=ctk.CTkFont(size=12)
        )
        self.monitor_dot.pack(side="left", padx=(0, 7))
        self.monitor_state_label = ctk.CTkLabel(
            left,
            text="MONITORING PAUSED",
            text_color=MUTED,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.monitor_state_label.pack(side="left")
        separator = ctk.CTkLabel(
            left, text="  /  ", text_color=MUTED, font=ctk.CTkFont(size=11)
        )
        separator.pack(side="left")
        self.internet_state_label = ctk.CTkLabel(
            left,
            text="INTERNET · WAITING",
            text_color=MUTED,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.internet_state_label.pack(side="left")
        self.monitor_button = ctk.CTkButton(
            self.toolbar,
            text="Start monitoring",
            width=150,
            height=34,
            corner_radius=9,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self.toggle_monitoring,
        )
        self.monitor_button.grid(row=0, column=1, sticky="e", padx=22, pady=13)

        self.page_host = ctk.CTkFrame(self.main_area, fg_color=BG, corner_radius=0)
        self.page_host.grid(row=1, column=0, sticky="nsew")
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)

    def _build_pages(self) -> None:
        page_types = {
            "Dashboard": DashboardPage,
            "Network information": NetworkInfoPage,
            "Ping & connectivity": ConnectivityPage,
            "Performance": PerformancePage,
            "Troubleshooting": TroubleshootingPage,
            "Settings": SettingsPage,
        }
        self.pages: dict[str, ctk.CTkFrame] = {}
        for name, page_type in page_types.items():
            page = page_type(self.page_host, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page
        self.pages[self.current_page].tkraise()

    def _refresh_navigation(self) -> None:
        for key, button in self.nav_buttons.items():
            active = key == self.current_page
            button.configure(
                fg_color=ACCENT if active else "transparent",
                hover_color=ACCENT_HOVER,
                text_color="#FFFFFF" if active else TEXT,
            )

    def show_page(self, name: str) -> None:
        if name not in self.pages:
            return
        self.current_page = name
        self.pages[name].tkraise()
        self._refresh_navigation()
        if name == "Network information":
            page = self.pages[name]
            if isinstance(page, NetworkInfoPage):
                page.refresh()
        elif name == "Settings":
            page = self.pages[name]
            if isinstance(page, SettingsPage):
                page.load_from_config(self.app_config)
        elif name == "Dashboard":
            page = self.pages[name]
            if isinstance(page, DashboardPage):
                page.chart.set_history(self.history, limit=45)
            if self.latest_network_info is None:
                self.refresh_network_info()
        elif name == "Performance":
            page = self.pages[name]
            if isinstance(page, PerformancePage):
                page.chart.set_history(self.history, limit=page.window_samples)

    def _enqueue_snapshot(self, snapshot: NetworkSnapshot) -> None:
        try:
            self._monitor_queue.put_nowait(snapshot)
        except queue.Full:
            try:
                self._monitor_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._monitor_queue.put_nowait(snapshot)
            except queue.Full:
                pass

    def _poll_monitor_queue(self) -> None:
        if self._closing:
            return
        latest: Optional[NetworkSnapshot] = None
        while True:
            try:
                latest = self._monitor_queue.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            self.latest_snapshot = latest
            self.history.append(latest)
            for page in self.pages.values():
                handler = getattr(page, "on_snapshot", None)
                if callable(handler):
                    try:
                        handler(latest)
                    except Exception:
                        logger.exception("Page snapshot update failed")
            self._update_toolbar(latest)
        self.after(180, self._poll_monitor_queue)

    def _update_toolbar(self, snapshot: Optional[NetworkSnapshot] = None) -> None:
        if self._monitor_requested:
            self.monitor_dot.configure(text_color=GREEN)
            self.monitor_state_label.configure(
                text="MONITORING ACTIVE", text_color=GREEN
            )
            self.monitor_button.configure(text="Pause monitoring")
        else:
            self.monitor_dot.configure(text_color=MUTED)
            self.monitor_state_label.configure(
                text="MONITORING PAUSED", text_color=MUTED
            )
            self.monitor_button.configure(text="Start monitoring")

        current = snapshot or self.latest_snapshot
        if current is None:
            self.internet_state_label.configure(
                text="INTERNET · WAITING", text_color=MUTED
            )
        elif current.internet_connected:
            self.internet_state_label.configure(
                text="INTERNET · CONNECTED", text_color=GREEN
            )
        else:
            self.internet_state_label.configure(
                text="INTERNET · DISCONNECTED", text_color=RED
            )

    def toggle_monitoring(self) -> None:
        if self._monitor_requested:
            self.pause_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self) -> None:
        if self._closing or self._monitor_requested:
            return
        self._monitor_requested = True
        self._update_toolbar()
        started = self.monitor.start(self._enqueue_snapshot)
        if not started:
            # A previous cycle may still be finishing a request when monitoring
            # is resumed. Retry without blocking the UI thread.
            self.after(250, self._retry_start_monitoring)

    def _retry_start_monitoring(self) -> None:
        if self._closing or not self._monitor_requested:
            return
        if self.monitor.is_running:
            self.after(250, self._retry_start_monitoring)
            return
        started = self.monitor.start(self._enqueue_snapshot)
        if not started:
            self.after(250, self._retry_start_monitoring)

    def pause_monitoring(self) -> None:
        self._monitor_requested = False
        self.monitor.stop(timeout=0)
        self._update_toolbar()

    def refresh_network_info(self) -> None:
        if self._closing or self._info_request_inflight:
            return
        self._info_request_inflight = True

        def finished(result: NetworkInfo | None, error: Exception | None) -> None:
            self._info_request_inflight = False
            if error is not None or result is None:
                logger.warning("Network information refresh failed: %s", error)
                return
            self.latest_network_info = result
            # The dashboard/performance summary does not request a public IP.
            # Keep the Network information page's on-demand public lookup intact.
            for name in ("Dashboard", "Performance"):
                page = self.pages.get(name)
                handler = getattr(page, "on_network_info", None)
                if callable(handler):
                    try:
                        handler(result)
                    except Exception:
                        logger.exception("Page network-info update failed")

        self.run_async(lambda: get_network_info(include_public=False), finished)

    def publish_network_info(self, info: NetworkInfo) -> None:
        """Broadcast a full on-demand network-info result to pages on the Tk thread."""
        self.latest_network_info = info
        for page in self.pages.values():
            handler = getattr(page, "on_network_info", None)
            if callable(handler):
                try:
                    handler(info)
                except Exception:
                    logger.exception("Page network-info update failed")

    def run_async(self, task: Callable, callback: Callable) -> None:
        """Run a callable in a worker and invoke callback(result, error) on Tk's thread."""
        if self._closing:
            return
        try:
            future: Future = self._executor.submit(task)
        except RuntimeError as exc:
            callback(None, exc)
            return

        def check_completion() -> None:
            if self._closing:
                return
            if not future.done():
                self.after(100, check_completion)
                return
            try:
                result = future.result()
            except Exception as exc:
                callback(None, exc)
            else:
                callback(result, None)

        self.after(70, check_completion)

    def save_settings(self, config: AppConfig):
        path = save_config(config)
        self.app_config = config
        self.monitor.update_settings(
            config.monitor_interval_seconds, config.probe_target
        )
        self._set_theme(config.theme)
        return path

    def _set_theme(self, theme: str) -> None:
        ctk.set_appearance_mode(theme)
        self._refresh_navigation()
        for page in self.pages.values():
            handler = getattr(page, "refresh_theme", None)
            if callable(handler):
                try:
                    handler()
                except Exception:
                    logger.exception("Could not refresh page theme")

    def clear_history(self) -> None:
        self.history.clear()
        for page in self.pages.values():
            handler = getattr(page, "refresh_theme", None)
            if callable(handler):
                handler()

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._monitor_requested = False
        self.monitor.stop(timeout=0)
        self._executor.shutdown(wait=False, cancel_futures=True)
        try:
            self.destroy()
        except Exception:
            logger.debug("Window was already destroyed", exc_info=True)
