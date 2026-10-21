"""Pure data transformations; this module NEVER writes to Firebase."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from typing import Any
import math

SAFE_STATES = {"NORMAL", "COOLING", "DOOR_ALARM", "TEMP_ALARM", "FAULT", "LIGHT_ALARM", "HUM_ALARM", "CLOUD_FAULT"}

def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        v = float(value)
        return v if math.isfinite(v) and v != -999 else None
    except (ValueError, TypeError, OverflowError):
        return None

def normalize_telemetry(raw: Any) -> dict:
    src = raw if isinstance(raw, dict) else {}
    t = number(src.get("temperature"))
    rh = number(src.get("humidity"))
    light = number(src.get("light_pct"))
    light_adc = number(src.get("light_adc", src.get("light_raw")))
    uptime = number(src.get("timestamp_ms", src.get("uptime_ms")))
    updated_at = number(src.get("updated_at"))
    state = str(src.get("state") or "UNKNOWN").upper()
    mode = str(src.get("mode") or "UNKNOWN").upper()
    return {
        "temperature": t,
        "humidity": rh,
        "light_pct": max(0.0, min(100.0, light)) if light is not None else None,
        "light_adc": light_adc,
        "door_open": src.get("door_open") if isinstance(src.get("door_open"), bool) else None,
        "cooler_on": src.get("cooler_on") if isinstance(src.get("cooler_on"), bool) else None,
        "alarm_led_on": (src.get("alarm_led_on", src.get("alarm_on")) if isinstance(src.get("alarm_led_on", src.get("alarm_on")), bool) else None),
        "buzzer_on": (src.get("buzzer_on", src.get("alarm_on")) if isinstance(src.get("buzzer_on", src.get("alarm_on")), bool) else None),
        "light_anomaly": bool(src.get("light_anomaly", src.get("light_alarm", False))),
        "humidity_warning": bool(src.get("humidity_warning", src.get("humidity_alarm", False))),
        "sensor_fault": bool(src.get("sensor_fault", state == "FAULT")),
        "mode": mode,
        "state": state,
        "door_violations": max(0, int(number(src.get("door_violations")) or 0)),
        "temp_violations": max(0, int(number(src.get("temp_violations")) or 0)),
        "uptime_ms": uptime,
        "updated_at": updated_at,  # Firebase server epoch MS, optional on legacy firmware
        "boot_id": str(src.get("boot_id") or ""),
        "data_available": bool(src),
    }

def normalize_events(raw: Any, limit: int = 120) -> list[dict]:
    if not isinstance(raw, dict):
        return []
    output = []
    for key, item in sorted(raw.items(), key=lambda pair: pair[0], reverse=True)[:limit]:
        if not isinstance(item, dict):
            continue
        uptime = number(item.get("timestamp_ms"))
        timestamp = number(item.get("timestamp"))
        dt = datetime.fromtimestamp(timestamp / 1000, timezone.utc).astimezone().strftime("%d %b %Y, %H:%M:%S") if timestamp and timestamp > 1_000_000_000_000 else "—"
        output.append({
            "Waktu server": dt,
            "Uptime ESP32": f"{uptime / 1000:.1f} dtk" if uptime is not None else "—",
            "Jenis": str(item.get("type", "UNKNOWN"))[:50],
            "Keterangan": str(item.get("detail", ""))[:300],
            "Event ID": str(key),
        })
    return output

def event_counts(events: list[dict]) -> dict[str, int]:
    return dict(Counter(e["Jenis"] for e in events))

def marker(snapshot: dict) -> tuple:
    # Uptime changes every PUT on original Wokwi code; boot_id disambiguates restarts if present.
    return (snapshot.get("boot_id"), snapshot.get("uptime_ms"), snapshot.get("updated_at"))

def connection_state(snapshot: dict, first_observed: float | None, last_change: float | None, now: float, threshold: int = 15) -> tuple[str, str]:
    if not snapshot.get("data_available"):
        return "EMPTY", "Belum ada telemetri dari Firebase"
    if first_observed is None:
        return "UNCHECKED", "Snapshot tersedia; aktivitas perangkat belum dapat dipastikan"
    if last_change is None:
        if now - first_observed > threshold:
            return "STALE", "Snapshot tidak berubah sejak dashboard dibuka"
        return "UNCHECKED", "Snapshot tersedia; menunggu perubahan dari ESP32"
    age = now - last_change
    if age <= threshold:
        return "FLOWING", "Telemetri berubah saat dashboard memantau"
    return "STALE", f"Tidak ada perubahan telemetri selama {int(age)} detik"

def sample_demo(base: dict, tick: int) -> dict:
    """Clearly synthetic educational data, NEVER sent to Firebase."""
    src = dict(base)
    src.update({"temperature": round(23.0 + 4.1 * math.sin(tick / 4.0), 1),
                "humidity": round(47 + 15 * math.sin(tick / 7.0), 1),
                "light_pct": round(45 + 32 * math.sin(tick / 5.5)),
                "timestamp_ms": tick * 3000,
                "boot_id": "LOCAL-DEMO"})
    src["cooler_on"] = src["temperature"] >= 24
    src["door_open"] = tick % 22 in (10, 11, 12, 13)
    src["light_anomaly"] = src["light_pct"] >= 64 and not src["door_open"]
    src["humidity_warning"] = src["humidity"] > 60
    src["state"] = "TEMP_ALARM" if src["temperature"] >= 25 else "COOLING" if src["cooler_on"] else "NORMAL"
    return normalize_telemetry(src)
