"""Smart Storage Room — Kelompok 3. `streamlit run app.py`.

LIVE: Wokwi <-> Firebase RTDB (/telemetry, /controls, /event_logs) <-> Streamlit
DEMO: local Python model, absolutely no Firebase requests or writes.
"""
from __future__ import annotations
import html
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_data import (device_freshness, effective_mode, firebase_time,
                            normalize_events, sensor_value, severity, uptime_label)
from demo import change, new_demo, snapshot, step, toggle_door
from firebase_client import AuthState, FirebaseClient, FirebaseError

st.set_page_config(page_title="Smart Storage Room | Kelompok 3", page_icon="🧊", layout="wide", initial_sidebar_state="expanded")
BASE = Path(__file__).parent
DEFAULTS = {
    "ui_theme": "Terang", "source_view": "Demo Lokal", "app_mode": "DEMO",
    "demo": None, "client": None, "auth": None, "dashboard": None,
    "samples": None, "last_temp_signature": None, "last_demo_tick": time.monotonic(),
    "last_good_read": None, "last_device_boot": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v
if st.session_state.demo is None:
    st.session_state.demo = new_demo()
if st.session_state.samples is None:
    st.session_state.samples = []

THEME = "dark" if st.session_state.ui_theme == "Gelap" else "light"
style = (BASE / "assets" / "theme.css").read_text(encoding="utf-8")
colors = (
    "--bg:#0b1727;--panel:#13243a;--sidebar:#101e31;--ink:#e4effe;"
    "--muted:#9ab1cd;--line:#2a405d;--brand:#71b2ff;--chip:#1a3250;"
    "--shade:rgba(70,135,220,.13);--shadow:0 8px 25px rgba(0,0,0,.12)"
    if THEME == "dark" else ""
)
st.markdown(f'<style>{style}:root{{color-scheme:{THEME};{colors}}}</style>', unsafe_allow_html=True)

def esc(s: object) -> str:
    return html.escape(str(s), quote=True)

def config() -> tuple[str, str] | None:
    try:
        fb = st.secrets.get("firebase", {})
        url = str(fb.get("database_url", "")).strip()
        key = str(fb.get("api_key", "")).strip()
        return (url, key) if url and key else None
    except Exception:
        return None

def clear_samples() -> None:
    st.session_state.samples = []
    st.session_state.last_temp_signature = None
    st.session_state.last_device_boot = None

def switch_source() -> None:
    st.session_state.app_mode = "DEMO" if st.session_state.source_view == "Demo Lokal" else "FIREBASE"
    clear_samples()

def login(email: str, password: str) -> None:
    fb = config()
    if fb is None:
        st.sidebar.error("Isi Firebase URL dan Web API Key di Streamlit Secrets terlebih dahulu.")
        return
    try:
        client = FirebaseClient(*fb)
        auth = client.sign_in(email, password)
        data, auth = client.read_dashboard(auth)
    except FirebaseError as exc:
        st.sidebar.error(str(exc))
        return
    st.session_state.client = client
    st.session_state.auth = auth
    st.session_state.dashboard = data
    st.session_state.last_good_read = datetime.now(ZoneInfo("Asia/Jakarta"))
    clear_samples()
    st.rerun()

def logout() -> None:
    st.session_state.client = None
    st.session_state.auth = None
    st.session_state.dashboard = None
    clear_samples()
    st.rerun()

with st.sidebar:
    st.markdown('<div class="sidebar-brand">◈ &nbsp; storage<span>room.</span></div>', unsafe_allow_html=True)
    st.caption("IoT LAB · KELOMPOK 3")
    st.divider()
    st.markdown("### Tampilan")
    st.radio("Tema", ["Terang", "Gelap"], key="ui_theme", horizontal=True,
             help="Tema untuk dashboard; tidak mengubah firmware atau Firebase.")
    st.markdown("### Sumber data")
    st.radio("Pilih lingkungan", ["Demo Lokal", "Simulasi Wokwi Live"],
             key="source_view", on_change=switch_source,
             help="Demo Lokal tidak mengakses Firebase. Mode Wokwi Live membaca perangkat nyata yang berjalan di simulator.")
    if st.session_state.app_mode == "DEMO":
        st.info("🧪 **Mode Demo:** semua nilai disimulasikan di Python, tidak dikirim ke Firebase.")
    else:
        st.markdown("#### Firebase Authentication")
        if st.session_state.auth is None:
            if config() is None:
                st.warning("Tambahkan `.streamlit/secrets.toml` atau Streamlit Cloud Secrets.")
            with st.form("signin", clear_on_submit=True):
                email = st.text_input("Email operator", placeholder="operator@example.com")
                password = st.text_input("Password operator", type="password")
                if st.form_submit_button("Masuk & hubungkan Firebase", type="primary", use_container_width=True):
                    login(email, password)
        else:
            auth: AuthState = st.session_state.auth
            st.success("Sesi Firebase aktif")
            st.caption(f"Operator: {auth.email}")
            st.button("Keluar Firebase", use_container_width=True, on_click=logout)
        st.caption("Wokwi harus sedang berjalan agar telemetri LIVE terus diperbarui.")
    st.divider()
    st.markdown("**Komponen yang dimonitor**")
    st.caption("DHT22 · LDR · Sakelar pintu · LED pendingin · LED alarm · Buzzer")
    st.caption("GPIO 4 / 34 / 32 / 26 / 25 / 27")
    st.caption("Pembaruan tampilan kira-kira 3 detik")

st.markdown('<div class="breadcrumbs">INTERNET OF THINGS &nbsp; / &nbsp; MKB 5A &nbsp; / &nbsp; KELOMPOK 3</div>', unsafe_allow_html=True)
left, right = st.columns([3.6, 1.1], vertical_alignment="center")
with left:
    st.markdown('<div class="eyebrow">SMART ENVIRONMENT MONITORING</div><h1 class="hero-title">Smart Storage Room<span>.</span></h1>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Monitor ruang penyimpanan, tinjau alarm, dan kendalikan pendingin melalui satu antarmuka.</div>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="device-id"><span>PERANGKAT</span><strong>ESP32 · STORAGE 03</strong><small>Wokwi + Firebase RTDB</small></div>', unsafe_allow_html=True)

if st.session_state.app_mode == "DEMO":
    st.warning("**DEMO LOKAL** — angka dan kejadian pada halaman ini dihasilkan Python, BUKAN data Firebase/Wokwi. Jangan dipakai sebagai bukti koneksi UTS.", icon="🧪")
else:
    st.info("**SIMULASI WOKWI LIVE** — data berasal dari Firebase. Perhatikan status heartbeat agar data lama tidak disangka live.", icon="📡")


def sample(data: dict, live: bool) -> None:
    t = data.get("telemetry")
    if not isinstance(t, dict):
        return
    temp = sensor_value(t.get("temperature"), -40, 80)
    if temp is None:
        return
    if live:
        boot = t.get("boot_id")
        if boot != st.session_state.last_device_boot:
            st.session_state.last_device_boot = boot
            clear_samples()
            st.session_state.last_device_boot = boot
        signature = (boot, t.get("updated_at"), t.get("timestamp_ms")) if t.get("updated_at") else tuple(sorted((k, str(v)) for k, v in t.items()))
    else:
        signature = (t.get("timestamp_ms"), t.get("state"), temp)
    if signature == st.session_state.last_temp_signature:
        return
    st.session_state.last_temp_signature = signature
    st.session_state.samples.append((datetime.now(ZoneInfo("Asia/Jakarta")), temp))
    del st.session_state.samples[:-70]


def read() -> tuple[dict, str | None]:
    if st.session_state.app_mode == "DEMO":
        now = time.monotonic()
        elapsed = now - st.session_state.last_demo_tick
        if elapsed >= 2.9:
            step(st.session_state.demo, max(3000, int(elapsed * 1000)))
            st.session_state.last_demo_tick = now
        return snapshot(st.session_state.demo), None
    if st.session_state.client is None or st.session_state.auth is None:
        return {}, "Masuk dengan akun operator Firebase untuk melihat simulasi Wokwi."
    try:
        data, auth = st.session_state.client.read_dashboard(st.session_state.auth)
        st.session_state.auth = auth
        st.session_state.dashboard = data
        st.session_state.last_good_read = datetime.now(ZoneInfo("Asia/Jakarta"))
        return data, None
    except FirebaseError as exc:
        return st.session_state.dashboard or {}, str(exc)


def metric(title: str, value: str, unit: str, hint: str, symbol: str, color: str, progress: float = 0) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-top"><span>{esc(title)}</span><b class="metric-icon {color}">{esc(symbol)}</b></div>'
        f'<div class="metric-reading">{esc(value)}<small>{esc(unit)}</small></div>'
        f'<div class="metric-hint"><i class="dot {color}"></i>{esc(hint)}</div>'
        f'<div class="metric-progress"><b class="{color}" style="width:{max(0,min(100,progress)):.0f}%"></b></div></div>',
        unsafe_allow_html=True)


def status_box(label: str, value: str, accent: str = "normal") -> None:
    st.markdown(f'<div class="status-cell"><span>{esc(label)}</span><strong class="{esc(accent)}">{esc(value)}</strong></div>', unsafe_allow_html=True)


def chart() -> None:
    st.markdown('<div class="section-kicker">TEMPERATURE TREND</div><div class="section-title">Riwayat temperatur</div>', unsafe_allow_html=True)
    st.caption("Sampel sejak halaman dibuka, bukan histori permanen Firebase")
    pts = st.session_state.samples
    if len(pts) < 2:
        st.markdown('<div class="empty-chart">Menunggu minimal dua pembacaan berbeda dari perangkat...</div>', unsafe_allow_html=True)
        return
    df = pd.DataFrame(pts, columns=["Waktu", "Suhu (°C)"])
    dark = st.session_state.ui_theme == "Gelap"
    grid = "#243955" if dark else "#e9eff7"
    ink = "#b9c9dd" if dark else "#69809c"
    fig = go.Figure(go.Scatter(x=df["Waktu"], y=df["Suhu (°C)"], mode="lines+markers",
                               line={"color": "#4b90f5", "width": 3}, marker={"size": 5},
                               fill="tozeroy", fillcolor="rgba(62,130,220,.10)",
                               hovertemplate="%{x|%H:%M:%S} WIB<br>%{y:.1f}°C<extra></extra>"))
    fig.add_hline(y=8, line_dash="dot", line_color="#d9a84f", annotation_text="Cooler ON · 8°C")
    fig.add_hline(y=12, line_dash="dot", line_color="#da777e", annotation_text="Alarm · 12°C")
    fig.update_layout(height=290, margin={"l": 8, "r": 12, "t": 24, "b": 8},
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
                      yaxis={"title": "°C", "gridcolor": grid, "zeroline": False},
                      xaxis={"tickformat": "%H:%M:%S", "showgrid": False},
                      font={"color": ink, "size": 11})
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, theme=None)


def send(patch: dict) -> None:
    if st.session_state.app_mode == "DEMO":
        if change(st.session_state.demo, **patch):
            st.toast("Perubahan hanya terjadi dalam DEMO LOKAL.", icon="🧪")
        else:
            st.warning("Perintah ditolak oleh interlock demo.")
        st.rerun(scope="fragment")
        return
    if st.session_state.client is None or st.session_state.auth is None:
        st.error("Login Firebase diperlukan.")
        return
    try:
        st.session_state.auth = st.session_state.client.write_controls(st.session_state.auth, patch)
        st.toast("Perintah tersimpan di Firebase; tunggu feedback /telemetry.", icon="📤")
        st.rerun(scope="fragment")
    except (FirebaseError, ValueError) as exc:
        st.error(str(exc))


def control_panel(data: dict, can_send_on: bool) -> None:
    st.markdown('<div class="section-kicker">REMOTE CONTROL</div><div class="section-title">Kontrol perangkat</div>', unsafe_allow_html=True)
    st.caption("Wokwi tetap menentukan apakah permintaan aman dijalankan")
    ctrl = data.get("controls") if isinstance(data.get("controls"), dict) else {}
    t = data.get("telemetry") if isinstance(data.get("telemetry"), dict) else {}
    mode = effective_mode(ctrl, t)
    actual = t.get("cooler_on")
    st.markdown("**Mode operasi**")
    a,b=st.columns(2)
    if a.button("✓ AUTO" if mode=="AUTO" else "AUTO", type="primary" if mode=="AUTO" else "secondary", use_container_width=True, key="auto"):
        send({"mode":"AUTO","manual_cooler_req":False})
    if b.button("✓ MANUAL" if mode=="MANUAL" else "MANUAL", type="primary" if mode=="MANUAL" else "secondary", use_container_width=True, key="manual"):
        send({"mode":"MANUAL","manual_cooler_req":False})
    st.markdown("**Perintah pendingin**")
    st.caption(f"Permintaan: **{'ON' if ctrl.get('manual_cooler_req') else 'OFF'}**  ·  Aktual ESP32: **{'ON' if actual is True else 'OFF' if actual is False else 'Belum ada data'}**")
    a,b=st.columns(2)
    if a.button("Nyalakan pendingin", key="coolon", use_container_width=True, disabled=mode!="MANUAL" or not can_send_on):
        send({"manual_cooler_req":True})
    if b.button("Matikan pendingin", key="cooloff", use_container_width=True, disabled=mode!="MANUAL"):
        send({"manual_cooler_req":False})
    if mode!="MANUAL":
        st.caption("Ubah mode ke MANUAL terlebih dahulu untuk mengirim perintah ON/OFF.")
    elif not can_send_on:
        st.warning("Perintah ON dinonaktifkan karena heartbeat Wokwi tidak terverifikasi atau interlock aktif.")
    st.divider()
    st.markdown("**Uji sensor tidak valid**")
    injected = ctrl.get("inject_sensor_fault") is True
    if injected:
        if st.button("Hentikan sensor fault", use_container_width=True, key="faultoff"):
            send({"inject_sensor_fault":False})
    else:
        ack=st.checkbox("Saya paham gangguan ini adalah simulasi", key="ack")
        if st.button("Aktifkan sensor fault", use_container_width=True, disabled=not ack, key="faulton"):
            send({"inject_sensor_fault":True})
    st.caption("Alarm pintu, suhu, kelembapan, dan cahaya dikendalikan oleh firmware; bukan tombol dashboard.")


def event_table(raw: object) -> None:
    st.markdown('<div class="section-kicker">SYSTEM HISTORY</div><div class="section-title">Log kejadian</div>', unsafe_allow_html=True)
    rows=[]
    for item in normalize_events(raw):
        rows.append({"Waktu Firebase":firebase_time(item.get("timestamp")),
                     "Event":str(item.get("type","EVENT")),
                     "Keterangan":str(item.get("detail","—")),
                     "Uptime":uptime_label(item.get("timestamp_ms")),
                     "Boot ID":str(item.get("boot_id","—"))})
    if rows:
        df=pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True, height=min(360,60+35*len(rows)))
        st.download_button("⬇ Unduh event log CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           file_name="smart_storage_events.csv", mime="text/csv", key="csv")
    else:
        st.info("Belum ada event. Jalankan simulasi atau gunakan kontrol dan sensor.")
    st.caption("Log dari firmware lama mungkin tidak memiliki waktu Firebase. Uptime ESP32 akan mulai ulang setelah restart.")


@st.fragment(run_every="3s")
def main_view() -> None:
    live = st.session_state.app_mode == "FIREBASE"
    data, err = read()
    if err:
        st.error("Firebase belum dapat dibaca: " + err + (" · Nilai cache di bawah adalah data lama." if data else ""))
    if not live:
        a,b,c,d,e=st.columns([1.0,1.0,1.0,1.0,1.8])
        if a.button("Suhu +2°C",key="tempplus",use_container_width=True):
            st.session_state.demo["temperature"] = min(50, st.session_state.demo["temperature"] + 2)
            step(st.session_state.demo,0)
        if b.button("Suhu −2°C",key="tempminus",use_container_width=True):
            st.session_state.demo["temperature"] = max(-20, st.session_state.demo["temperature"] - 2)
            step(st.session_state.demo,0)
        if c.button("Pintu buka/tutup",key="door",use_container_width=True):
            toggle_door(st.session_state.demo)
        if d.button("Reset Demo",key="demoreset",use_container_width=True):
            st.session_state.demo = new_demo()
            clear_samples()
            st.session_state.last_demo_tick = time.monotonic()
            st.rerun(scope="fragment")
        e.caption("Uji manual demo melalui kontrol di panel bawah. Semua berjalan lokal.")
    t=data.get("telemetry") if isinstance(data.get("telemetry"),dict) else {}
    now_ms=int(time.time()*1000)
    status, age = (device_freshness(t, now_ms) if live else ("DEMO",None))
    if live:
        if err:
            st.error("Status: FETCH FAILED — tidak bisa memastikan koneksi ESP32 saat ini.")
        elif status=="ONLINE":
            st.success(f"● WOKWI ONLINE · Paket telemetri terakhir {age/1000:.1f} detik lalu · Sinkronisasi ≈3 detik")
        elif status=="STALE":
            st.warning(f"● DATA LAMA · Wokwi tidak mengirim data selama {age/1000:.0f} detik. Periksa simulasi dan Wi-Fi.")
        elif status=="UNKNOWN":
            st.warning("● HEARTBEAT BELUM TERSEDIA · Data mungkin berasal dari firmware/export lama (tidak ada updated_at).")
        else:
            st.warning("● BELUM ADA TELEMETRI · Jalankan Wokwi dan lihat Serial Monitor.")
    else:
        st.caption("● DEMO LOKAL · Python simulation · tidak menggunakan koneksi Firebase")
    sample(data,live and not bool(err) and status=="ONLINE") if (not live or (not err and status=="ONLINE")) else None
    temp=sensor_value(t.get("temperature"),-40,80)
    hum=sensor_value(t.get("humidity"),0,100)
    light=sensor_value(t.get("light_pct"),0,100)
    door=t.get("door_open") if isinstance(t.get("door_open"),bool) else None
    st.markdown('<div class="section-label">KONDISI RUANG PENYIMPANAN</div>',unsafe_allow_html=True)
    cols=st.columns(4,gap="small")
    with cols[0]:metric("Suhu ruangan",f"{temp:.1f}" if temp is not None else "—","°C","Ambang pendingin 8°C","🌡","warm",(temp or 0)*4)
    with cols[1]:metric("Kelembapan",f"{hum:.0f}" if hum is not None else "—","%","Alarm mulai 60% RH","💧","blue",hum or 0)
    with cols[2]:metric("Intensitas cahaya",f"{light:.0f}" if light is not None else "—","%","LDR simulasi","☀","purple",light or 0)
    with cols[3]:metric("Sakelar pintu","TERBUKA" if door is True else "TERTUTUP" if door is False else "—","","Alarm setelah 10 detik","🚪","green" if door is False else "warm",100 if door else 20)
    st.markdown('<div class="space"></div>',unsafe_allow_html=True)
    s=st.columns(4,gap="small")
    with s[0]:status_box("STATE MACHINE",str(t.get("state","—")),severity(t.get("state")))
    with s[1]:status_box("PENDINGIN AKTUAL","ON" if t.get("cooler_on") is True else "OFF" if t.get("cooler_on") is False else "—","active" if t.get("cooler_on") is True else "normal")
    with s[2]:status_box("MODE AKTUAL",str(t.get("mode","—")))
    with s[3]:status_box("TOTAL PELANGGARAN",str(sum(int(t.get(k,0)) for k in ("door_violations","temp_violations","humidity_violations") if isinstance(t.get(k,0),int))))
    st.markdown('<div class="space"></div>',unsafe_allow_html=True)
    a,b=st.columns([1.35,1],gap="medium")
    with a:
        with st.container(border=True):
            chart()
            st.caption("Suhu dan interlock dicocokkan dengan ambang firmware Wokwi: 8/5°C dan alarm 12/10°C.")
            st.markdown("**Indikator alarm**")
            badges=[]
            for key,label in (("temp_alarm","Suhu"),("humidity_alarm","Kelembapan"),("door_alarm","Pintu"),("light_alarm","Cahaya"),("sensor_fault","Sensor"),("cloud_fault","Firebase")):
                badges.append((label,"AKTIF" if t.get(key) is True else "Aman" if t.get(key) is False else "—"))
            rows=st.columns(3)
            for idx,(label,val) in enumerate(badges):
                with rows[idx%3]:status_box(label,val,"danger" if val=="AKTIF" else "normal")
    with b:
        with st.container(border=True):
            can_on = (not live or (not err and status=="ONLINE")) and not any(t.get(key) is True for key in ("sensor_fault","cloud_fault","door_open","light_alarm"))
            control_panel(data,can_on)
    with st.container(border=True):
        event_table(data.get("events"))
    if live and st.session_state.last_good_read:
        st.caption("Firebase terakhir berhasil dibaca: " + st.session_state.last_good_read.strftime("%d %b %Y · %H:%M:%S WIB"))

main_view()
st.markdown('<div class="footer">Smart Storage Room · Kelompok 3 · ESP32 + Firebase Realtime Database + Streamlit · Untuk simulasi akademik</div>', unsafe_allow_html=True)
