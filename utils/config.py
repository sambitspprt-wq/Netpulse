"""User settings with sane bounds and atomic JSON persistence."""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.ping_service import validate_target


@dataclass(frozen=True, slots=True)
class AppConfig:
    monitor_interval_seconds: float = 3.0
    probe_target: str = "1.1.1.1"
    theme: str = "dark"
    auto_start_monitoring: bool = True


DEFAULT_CONFIG = AppConfig()


def config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "NetworkMonitor" / "config.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "network_monitor" / "config.json"


def _sanitize(data: dict[str, Any]) -> AppConfig:
    try:
        interval = float(
            data.get(
                "monitor_interval_seconds", DEFAULT_CONFIG.monitor_interval_seconds
            )
        )
    except (TypeError, ValueError):
        interval = DEFAULT_CONFIG.monitor_interval_seconds
    if not math.isfinite(interval):
        interval = DEFAULT_CONFIG.monitor_interval_seconds
    interval = max(2.0, min(interval, 60.0))

    target = str(data.get("probe_target", DEFAULT_CONFIG.probe_target)).strip()
    try:
        target = validate_target(target)
    except ValueError:
        target = DEFAULT_CONFIG.probe_target

    theme = str(data.get("theme", DEFAULT_CONFIG.theme)).lower()
    if theme not in {"dark", "light", "system"}:
        theme = DEFAULT_CONFIG.theme

    auto_start = data.get("auto_start_monitoring", DEFAULT_CONFIG.auto_start_monitoring)
    if not isinstance(auto_start, bool):
        auto_start = DEFAULT_CONFIG.auto_start_monitoring

    return AppConfig(interval, target, theme, auto_start)


def load_config() -> AppConfig:
    path = config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return _sanitize(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        pass
    return DEFAULT_CONFIG


def save_config(config: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    temporary.replace(path)
    return path
