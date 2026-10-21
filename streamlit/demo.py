"""Deterministic local-only Wokwi-like demonstration. Never uses Firebase."""
from __future__ import annotations


def new_demo() -> dict:
    return {
        "temperature": 6.5, "humidity": 44.0, "light_pct": 25,
        "door_open": False, "cooler_on": False, "cooler_wanted": False,
        "door_alarm": False, "temp_alarm": False, "humidity_alarm": False,
        "light_alarm": False, "sensor_fault": False, "cloud_fault": False,
        "alarm_on": False, "door_violations": 0, "temp_violations": 0,
        "humidity_violations": 0, "mode": "AUTO", "manual_cooler_req": False,
        "inject_sensor_fault": False, "state": "NORMAL", "timestamp_ms": 0,
        "door_open_ms": 0, "events": [], "boot_id": "LOCAL-DEMO",
    }


def event(d: dict, kind: str, detail: str) -> None:
    d["events"].insert(0, {"type": kind, "detail": f"[DEMO] {detail}",
                            "timestamp_ms": d["timestamp_ms"], "boot_id": "LOCAL-DEMO"})
    del d["events"][60:]


def step(d: dict, elapsed_ms: int = 3000) -> None:
    d["timestamp_ms"] += elapsed_ms
    t = d["temperature"]
    if not d["cooler_wanted"] and t >= 8:
        d["cooler_wanted"] = True
    elif d["cooler_wanted"] and t <= 5:
        d["cooler_wanted"] = False
    if not d["temp_alarm"] and t >= 12:
        d["temp_alarm"] = True
        d["temp_violations"] += 1
        event(d, "ALARM_TEMP", "Suhu ≥12°C")
    elif d["temp_alarm"] and t <= 10:
        d["temp_alarm"] = False
        event(d, "ALARM_CLEAR", "Suhu ≤10°C")
    if not d["humidity_alarm"] and d["humidity"] >= 60:
        d["humidity_alarm"] = True
        d["humidity_violations"] += 1
        event(d, "ALARM_HUM", "RH ≥60%")
    elif d["humidity_alarm"] and d["humidity"] <= 55:
        d["humidity_alarm"] = False
        event(d, "HUM_NORMAL", "RH ≤55%")
    bright = not d["door_open"] and (d["light_pct"] >= 55 if not d["light_alarm"] else d["light_pct"] > 45)
    if bright != d["light_alarm"]:
        event(d, "LIGHT_ANOMALY" if bright else "LIGHT_NORMAL", "Perubahan intensitas cahaya")
    d["light_alarm"] = bright
    if d["door_open"] and not d["door_alarm"] and d["timestamp_ms"] - d["door_open_ms"] >= 10000:
        d["door_alarm"] = True
        d["door_violations"] += 1
        event(d, "ALARM_DOOR", "Pintu >10 detik")
    requested = d["cooler_wanted"] if d["mode"] == "AUTO" else d["manual_cooler_req"]
    blocked = d["sensor_fault"] or d["cloud_fault"] or d["door_open"] or d["light_alarm"]
    new_cooler = bool(requested and not blocked)
    if new_cooler != d["cooler_on"]:
        event(d, "COOLER_ON" if new_cooler else "COOLER_OFF", "Interlock diterapkan")
    d["cooler_on"] = new_cooler
    new_state = ("FAULT" if d["sensor_fault"] or d["cloud_fault"] else
                 "DOOR_ALARM" if d["door_alarm"] else
                 "TEMP_ALARM" if d["temp_alarm"] else
                 "HUM_ALARM" if d["humidity_alarm"] else
                 "LIGHT_ALARM" if d["light_alarm"] else
                 "COOLING" if d["cooler_on"] else "NORMAL")
    if new_state != d["state"]:
        event(d, "STATE", f"{d['state']} → {new_state}")
    d["state"] = new_state
    d["alarm_on"] = d["sensor_fault"] or d["cloud_fault"] or d["door_alarm"] or d["temp_alarm"] or d["humidity_alarm"] or d["light_alarm"]


def change(d: dict, **kwargs: object) -> bool:
    if "mode" in kwargs:
        mode = kwargs["mode"]
        if mode not in ("AUTO", "MANUAL"):
            raise ValueError("Invalid mode")
        if d["mode"] != mode:
            d["mode"] = mode
            d["manual_cooler_req"] = False
            event(d, "MODE_CHANGE", f"Mode {mode}")
    if "manual_cooler_req" in kwargs:
        request = kwargs["manual_cooler_req"]
        if d["mode"] != "MANUAL" or (request and (d["sensor_fault"] or d["cloud_fault"] or d["door_open"] or d["light_alarm"])):
            event(d, "CMD_REJECTED", "Mode atau interlock menolak perintah")
            return False
        d["manual_cooler_req"] = bool(request)
        event(d, "MANUAL_COMMAND", "ON" if request else "OFF")
    if "inject_sensor_fault" in kwargs:
        d["inject_sensor_fault"] = bool(kwargs["inject_sensor_fault"])
        d["sensor_fault"] = d["inject_sensor_fault"]
        event(d, "FAULT_INJECT", "Sensor fault disimulasikan")
    step(d, elapsed_ms=0)
    return True


def toggle_door(d: dict) -> None:
    d["door_open"] = not d["door_open"]
    if d["door_open"]:
        d["door_open_ms"] = d["timestamp_ms"]
        event(d, "DOOR_OPEN", "Pintu dibuka")
    else:
        d["door_alarm"] = False
        event(d, "DOOR_CLOSED", "Pintu ditutup")
    step(d, elapsed_ms=0)


def snapshot(d: dict) -> dict:
    fields = (
        "temperature", "humidity", "light_pct", "door_open", "cooler_on",
        "mode", "state", "door_violations", "temp_violations", "humidity_violations",
        "door_alarm", "temp_alarm", "humidity_alarm", "light_alarm", "sensor_fault",
        "cloud_fault", "alarm_on", "timestamp_ms", "boot_id",
    )
    return {"telemetry": {k: d[k] for k in fields},
            "controls": {k: d[k] for k in ("mode", "manual_cooler_req", "inject_sensor_fault")},
            "events": d["events"]}
