"""Pure formatting & heartbeat functions for Python dashboard."""
from __future__ import annotations
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

def sensor_value(value: Any, minimum: float | None = None, maximum: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value == -999:
        return None
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return float(value)

def device_freshness(telemetry: Any, now_ms: int, threshold_ms: int = 16000) -> tuple[str, int | None]:
    """UNKNOWN for legacy RTDB exports lacking `updated_at`; never claim online."""
    if not isinstance(telemetry, dict):
        return "NO_DATA", None
    updated = sensor_value(telemetry.get("updated_at"), 1)
    if updated is None:
        return "UNKNOWN", None
    age = max(0, now_ms - int(updated))
    return ("ONLINE" if age <= threshold_ms else "STALE"), age

def uptime_label(value: Any) -> str:
    ms = sensor_value(value, 0)
    if ms is None:
        return "—"
    total = int(ms // 1000)
    return f"{total // 60:02d}:{total % 60:02d}"

def firebase_time(value: Any) -> str:
    stamp = sensor_value(value, 1)
    if stamp is None:
        return "—"
    return datetime.fromtimestamp(stamp / 1000, ZoneInfo("Asia/Jakarta")).strftime("%d/%m %H:%M:%S WIB")

def normalize_events(raw: Any, limit: int = 60) -> list[dict]:
    if isinstance(raw, dict):
        return [v for _, v in sorted(raw.items(), key=lambda x: x[0], reverse=True) if isinstance(v, dict)][:limit]
    if isinstance(raw, list):
        return [v for v in reversed(raw) if isinstance(v, dict)][:limit]
    return []

def effective_mode(controls: Any, telemetry: Any) -> str:
    if isinstance(controls, dict) and controls.get("mode") in ("AUTO", "MANUAL"):
        return controls["mode"]
    if isinstance(telemetry, dict) and telemetry.get("mode") in ("AUTO", "MANUAL"):
        return telemetry["mode"]
    return "AUTO"

def severity(state: Any) -> str:
    s = str(state or "").upper()
    if "FAULT" in s or "ALARM" in s:
        return "danger"
    if s == "COOLING":
        return "active"
    return "normal"
