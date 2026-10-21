"""Smart Medicine Storage Monitoring and Alarm Management System — Kelompok 3 | READ-ONLY Streamlit monitoring."""
from __future__ import annotations
from datetime import datetime
from html import escape
import json
from pathlib import Path
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.firebase_reader import FirebaseReader, FirebaseReadError
from src.model import normalize_telemetry, normalize_events, event_counts, marker, sample_demo, connection_state

ROOT = Path(__file__).parent
st.set_page_config(page_title="Smart Storage | Monitoring", page_icon="🧊", layout="wide", initial_sidebar_state="expanded")

PALETTES = {
    "Terang": {"bg": "#F6F8FC", "panel": "#FFFFFF", "panel_alt": "#EEF4FF", "ink": "#172844", "muted": "#60718B", "line": "#DCE5F2", "blue": "#266DEB", "green": "#13866D", "red": "#CB4552", "amber": "#B06C09", "plot": "#FFFFFF"},
    "Gelap": {"bg": "#0B1424", "panel": "#152238", "panel_alt": "#1B2C49", "ink": "#F3F6FE", "muted": "#A9BAD2", "line": "#31445D", "blue": "#70B6FF", "green": "#5EDEBD", "red": "#FF8997", "amber": "#F3C17A", "plot": "#152238"},
}

def theme_css(p):
    return f"""<style>
    .stApp, [data-testid="stAppViewContainer"] {{ background:{p['bg']}; color:{p['ink']}; }}
    [data-testid="stSidebar"] {{ background:{p['panel']}; border-right:1px solid {p['line']}; }}
    [data-testid="stSidebar"] * {{ color:{p['ink']}; }}
    [data-testid="stHeader"] {{ background:transparent; }}
    .block-container {{ padding-top:2.1rem; padding-bottom:3.5rem; max-width:1480px; }}
    h1,h2,h3,p,span,label {{ color:inherit; }}
    .ss-hero {{background:linear-gradient(105deg,#0C3580 0%,#1556B4 54%,#277DDB 100%);color:#fff;border-radius:22px;padding:27px 31px 29px;margin:0 0 22px;position:relative;overflow:hidden;box-shadow:0 10px 35px rgba(12,53,128,.10)}}
    .ss-hero:after {{content:'';position:absolute;width:330px;height:330px;border:1px solid rgba(255,255,255,.18);border-radius:50%;right:-75px;top:-145px;box-shadow:0 0 0 65px rgba(255,255,255,.045),0 0 0 125px rgba(255,255,255,.035);pointer-events:none}}
    .ss-eyebrow {{letter-spacing:.14em;text-transform:uppercase;font-size:.72rem;font-weight:800;opacity:.82;color:#E8F3FF}}
    .ss-hero h1 {{font-size:clamp(1.58rem,2.2vw,2.42rem);letter-spacing:-.035em;margin:7px 0 8px;color:white;line-height:1.18}}
    .ss-hero p {{font-size:.97rem;color:#DFEBFF;max-width:750px;margin:0}}
    .ss-small {{font-size:.82rem;color:{p['muted']};}}
    .ss-card {{background:{p['panel']};border:1px solid {p['line']};border-radius:18px;padding:20px 21px;min-height:132px;box-shadow:0 4px 20px rgba(12,38,78,.025);margin-bottom:8px}}
    .ss-card .ss-label {{text-transform:uppercase;letter-spacing:.065em;font-size:.72rem;font-weight:800;color:{p['muted']};}}
    .ss-card .ss-val {{font-weight:800;font-size:clamp(1.6rem,2vw,2.15rem);letter-spacing:-.04em;line-height:1.35;color:{p['ink']};}}
    .ss-card .ss-sub {{color:{p['muted']};font-size:.79rem;}}
    .ss-chip {{display:inline-block;padding:5px 11px;border-radius:30px;font-size:.78rem;font-weight:750;background:{p['panel_alt']};color:{p['blue']};border:1px solid {p['line']};}}
    .ss-status {{background:{p['panel']};border:1px solid {p['line']};padding:15px 19px;border-radius:15px;margin:1px 0 20px;color:{p['ink']};}}
    .ss-section {{font-size:1.11rem;font-weight:800;color:{p['ink']};margin:18px 0 10px;}}
    .ss-condition {{border:1px solid {p['line']};background:{p['panel']};border-radius:14px;padding:16px;margin-bottom:5px;min-height:100px}}
    .ss-condition strong {{display:block;font-size:.92rem;color:{p['ink']};margin-bottom:3px}}
    .ss-condition span {{font-size:.84rem;color:{p['muted']};}}
    div[data-testid="stPlotlyChart"] {{ background:{p['plot']};border:1px solid {p['line']};border-radius:18px;padding:7px; }}
    div[data-testid="stMetric"] {{background:{p['panel']};padding:14px;border:1px solid {p['line']};border-radius:15px}}
    [data-testid="stWidgetLabel"] {{color:{p['ink']};}}
    .ss-footer {{margin-top:25px;border-top:1px solid {p['line']};padding-top:13px;color:{p['muted']};font-size:.79rem;}}
    @media(max-width:660px) {{.ss-hero{{padding:22px 20px}}.ss-card{{padding:16px;min-height:120px}}.block-container{{padding-top:1.2rem}}}}
    </style>"""

def card(label, value, foot):
    return f'<div class="ss-card"><div class="ss-label">{escape(label)}</div><div class="ss-val">{escape(str(value))}</div><div class="ss-sub">{escape(foot)}</div></div>'

def fmt(value, unit="", digits=1):
    return "—" if value is None else f"{value:.{digits}f}{unit}"

def glyph_condition(title, value, detail):
    return f'<div class="ss-condition"><strong>{escape(title)}</strong><span>{escape(value)} · {escape(detail)}</span></div>'

def plot_base(p, title, height=295):
    fig=go.Figure()
    fig.update_layout(title=dict(text=title,font=dict(size=15,color=p["ink"])),height=height,
        paper_bgcolor=p["plot"], plot_bgcolor=p["plot"],font=dict(color=p["ink"],size=12),
        margin=dict(l=14,r=13,t=48,b=20),showlegend=False,
        xaxis=dict(showgrid=False,zeroline=False),yaxis=dict(gridcolor=p["line"],zeroline=False))
    return fig

def get_settings():
    try:
        config = st.secrets.get("firebase", {})
        return dict(config)
    except Exception:
        return {}

settings=get_settings()
with st.sidebar:
    st.markdown("### 🧊 Smart Medicine Storage Monitoring and Alarm Management System")
    st.caption("Internet of Things · Kelompok 3")
    st.divider()
    st.markdown("**Sumber data**")
    source=st.radio("Pilih sumber", ["📡 Firebase Live", "🧪 Demo Lokal"], index=0 if all(settings.get(k) for k in ("database_url","api_key","refresh_token")) else 1, help="Firebase Live hanya membaca database. Demo Lokal menggunakan data simulasi.")
    st.markdown("**Tampilan**")
    selected_theme=st.radio("Tema dashboard", ["☀️ Terang", "🌙 Gelap"], horizontal=True)
    st.divider()
    st.caption("**READ-ONLY DASHBOARD**")
    st.info("Dashboard hanya memonitor. Semua kendali sensor dan aktuator tetap di Wokwi.",icon="🔒")
    st.caption("Pembaruan tampilan otomatis ±3 detik selama halaman aktif.")
    if source == "📡 Firebase Live" and not all(settings.get(k) for k in ("database_url","api_key","refresh_token")):
        st.warning("Konfigurasi Firebase belum lengkap. Lihat docs/INSTALL_RUN_SECRETS.txt.")

theme="Gelap" if "Gelap" in selected_theme else "Terang"
p=PALETTES[theme]
st.markdown(theme_css(p),unsafe_allow_html=True)

st.markdown('<div class="ss-hero"><div class="ss-eyebrow">Kelompok 3 · IoT Monitoring System</div><h1>Smart Medicine Storage Monitoring and Alarm Management System</h1><p>Pemantauan kondisi ruang penyimpanan, aktivitas pendingin, dan manajemen alarm — dari Wokwi melalui Firebase Realtime Database.</p></div>',unsafe_allow_html=True)

if st.session_state.get("source_key") != source:
    st.session_state["source_key"]=source
    for k in ("series", "seen_marker", "first_seen", "last_changed", "last_data", "last_events", "reader", "demo_tick"):
        st.session_state.pop(k,None)

@st.fragment(run_every="3s")
def render_dashboard():
    snap={}; events=[]; failure=None
    is_demo=source=="🧪 Demo Lokal"
    now=time.time()
    if is_demo:
        sample=json.loads((ROOT/"data"/"demo_snapshot.json").read_text(encoding="utf-8"))
        step=st.session_state.get("demo_tick",0)
        st.session_state["demo_tick"]=step+1
        snap=sample_demo(sample.get("telemetry",{}),step)
        events=normalize_events(sample.get("event_logs",{}))
        connection="DEMO"
        connection_text="Data contoh hasil simulasi lokal; tidak terhubung ke Firebase"
    elif not all(settings.get(k) for k in ("database_url","api_key","refresh_token")):
        failure="Firebase belum dikonfigurasi pada Streamlit Secrets."
        connection="CONFIG"
        connection_text=failure
    else:
        try:
            if "reader" not in st.session_state:
                st.session_state["reader"]=FirebaseReader(settings["database_url"],settings["api_key"],settings["refresh_token"])
            raw, raw_events=st.session_state["reader"].fetch()
            snap=normalize_telemetry(raw)
            events=normalize_events(raw_events)
            st.session_state["last_data"]=snap
            st.session_state["last_events"]=events
            current_marker=marker(snap)
            if snap["data_available"]:
                if "first_seen" not in st.session_state:
                    st.session_state["first_seen"]=now
                if "seen_marker" in st.session_state and current_marker != st.session_state["seen_marker"]:
                    st.session_state["last_changed"]=now
                st.session_state["seen_marker"]=current_marker
            connection,connection_text=connection_state(snap,st.session_state.get("first_seen"),st.session_state.get("last_changed"),now)
            if snap.get("updated_at") is not None:
                age=now - snap["updated_at"]/1000
                if age>15:
                    connection="STALE";connection_text=f"Data Firebase terakhir diperbarui {int(age)} detik lalu"
                elif age>=-5:
                    connection="FLOWING";connection_text="Timestamp pembaruan dari server Firebase tersedia"
        except (FirebaseReadError,ValueError) as exc:
            failure=str(exc)
            snap=st.session_state.get("last_data",{})
            events=st.session_state.get("last_events",[])
            connection="ERROR";connection_text="Pembacaan terbaru gagal; nilai lama tidak dinyatakan sebagai data live"

    badge={"DEMO":"🧪 DEMO LOKAL", "FLOWING":"🟢 DATA MENGALIR", "UNCHECKED":"🟡 MENUNGGU PEMBARUAN", "STALE":"🟠 DATA LAMA", "EMPTY":"⚪ DATA KOSONG", "ERROR":"🔴 GAGAL MEMBACA", "CONFIG":"⚪ BELUM DIKONFIGURASI"}.get(connection,"⚪ STATUS")
    st.markdown(f'<div class="ss-status"><strong>{escape(badge)}</strong>&nbsp;&nbsp; <span class="ss-small">{escape(connection_text)}</span></div>',unsafe_allow_html=True)
    if failure:
        st.error(failure)
    elif connection=="STALE":
        st.warning("Perangkat mungkin berhenti, Wokwi dijeda, atau jalur Firebase bermasalah. Periksa Serial Monitor.")

    columns=st.columns(4)
    metrics=[("🌡️ Suhu",fmt(snap.get("temperature")," °C"),"DHT22 · temperatur"),
             ("💧 Kelembapan",fmt(snap.get("humidity")," %"),"DHT22 · kelembapan relatif"),
             ("☀️ Intensitas Cahaya",fmt(snap.get("light_pct")," %",0),"LDR · skala simulasi"),
             ("🧊 Pendingin","ON" if snap.get("cooler_on") else "OFF" if snap.get("cooler_on") is False else "—","Status LED biru dari ESP32")]
    for col,(label,value,foot) in zip(columns,metrics):
        with col: st.markdown(card(label,value,foot),unsafe_allow_html=True)

    st.markdown('<div class="ss-section">Status ruang penyimpanan</div>',unsafe_allow_html=True)
    s=st.columns([1.15,1,1,1.15])
    details=[("⚙️ State Machine",snap.get("state","UNKNOWN"),"Status hasil logika Wokwi"),
             ("🚪 Kondisi Pintu","TERBUKA" if snap.get("door_open") else "TERTUTUP" if snap.get("door_open") is False else "—","Sakelar pintu"),
             ("🚨 Alarm","AKTIF" if (snap.get("alarm_led_on") or snap.get("buzzer_on")) else "NONAKTIF","LED merah / buzzer"),
             ("🔁 Mode ESP32",snap.get("mode","—"),"Informasi saja; tidak bisa diubah di sini")]
    for col,(label,value,foot) in zip(s,details):
        with col: st.markdown(glyph_condition(label,value,foot),unsafe_allow_html=True)

    alerts=st.columns(4)
    conditions=[("Suhu", "TINGGI" if snap.get("state")=="TEMP_ALARM" else "—", "Ambang firmware: 25°C (alarm ON)"),
                ("Cahaya", "ANOMALI" if snap.get("light_anomaly") else "NORMAL", "Cahaya saat pintu tertutup"),
                ("Kelembapan", "PERINGATAN" if snap.get("humidity_warning") else "NORMAL", "Alarm jika RH > 60%"),
                ("Sensor", "FAULT" if snap.get("sensor_fault") else "VALID", "Validitas DHT22")]
    for col,(label,value,foot) in zip(alerts,conditions):
        with col: st.markdown(glyph_condition(label,value,foot),unsafe_allow_html=True)

    tab_over,tab_events,tab_about=st.tabs(["📊 Statistik & Grafik", "📋 Riwayat Kejadian", "ℹ️ Informasi Sistem"])
    with tab_over:
        st.caption("Grafik memperlihatkan sampel selama halaman terbuka. Firmware menimpa `/telemetry` setiap sinkronisasi; data historis sebelum dashboard dibuka tidak tersedia dari path ini.")
        if snap.get("data_available") and not failure:
            rec={"Waktu dibaca":datetime.now().astimezone(), "Suhu (°C)":snap.get("temperature"), "Kelembapan (%)":snap.get("humidity"), "Cahaya (%)":snap.get("light_pct")}
            points=st.session_state.setdefault("series",[])
            if is_demo or ("seen_marker" in st.session_state):
                # A new point per Streamlit update. This is dashboard observation time, not an ESP32 measurement timestamp.
                points.append(rec)
                if len(points)>90: del points[:-90]
        points=st.session_state.get("series",[])
        left,right=st.columns([1.65,1])
        with left:
            fig=plot_base(p,"Tren suhu yang diamati")
            df=pd.DataFrame(points)
            if not df.empty:
                fig.add_trace(go.Scatter(x=df["Waktu dibaca"],y=df["Suhu (°C)"],mode="lines+markers",line=dict(color=p["blue"],width=3),marker=dict(size=5),fill="tozeroy",fillcolor="rgba(52,130,245,.10)"))
                fig.add_hline(y=25,line_dash="dash",line_color=p["red"],annotation_text="Alarm ON 25°C",annotation_position="top right")
            else:
                fig.add_annotation(text="Menunggu sampel dashboard...",xref="paper",yref="paper",x=.5,y=.5,showarrow=False,font=dict(color=p["muted"]))
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        with right:
            st.markdown('<div class="ss-section">Ringkasan pelanggaran</div>',unsafe_allow_html=True)
            v1,v2=st.columns(2)
            with v1: st.metric("Pintu", snap.get("door_violations") if snap else "—")
            with v2: st.metric("Suhu", snap.get("temp_violations") if snap else "—")
            st.caption("Penghitung berasal dari telemetri ESP32 dan dapat direset saat Wokwi di-restart.")
            st.markdown(f'<div class="ss-status"><strong>📷 Snapshot</strong><div class="ss-small">ADC cahaya: {escape(str(snap.get("light_adc") if snap.get("light_adc") is not None else "—"))} · Uptime: {escape(fmt(snap.get("uptime_ms")/1000 if snap.get("uptime_ms") is not None else None," detik",1))}</div></div>',unsafe_allow_html=True)
        fig2=plot_base(p,"Tren kelembapan dan tingkat cahaya (pengamatan dashboard)",height=275)
        if points:
            df=pd.DataFrame(points)
            for field,color in [("Kelembapan (%)",p["green"]),("Cahaya (%)",p["amber"])]:
                fig2.add_trace(go.Scatter(x=df["Waktu dibaca"],y=df[field],mode="lines",line=dict(color=color,width=2.5),name=field))
            fig2.update_layout(showlegend=True,legend=dict(orientation="h",y=1.12,x=0))
            fig2.update_yaxes(range=[0,100])
        st.plotly_chart(fig2,use_container_width=True,config={"displayModeBar":False})
    with tab_events:
        st.caption("Data dari `/event_logs`. Urutan berdasarkan Firebase push ID. `timestamp_ms` adalah uptime ESP32, **bukan waktu kalender**; event lama bisa berasal dari beberapa restart.")
        if events:
            types=sorted(set(e["Jenis"] for e in events))
            selected=st.multiselect("Filter jenis kejadian",types,default=[],placeholder="Semua kejadian",key="event_filter")
            shown=[e for e in events if not selected or e["Jenis"] in selected]
            st.dataframe(pd.DataFrame(shown)[["Waktu server","Uptime ESP32","Jenis","Keterangan"]],use_container_width=True,hide_index=True,height=390)
            st.download_button("⬇️ Unduh event log (CSV)",data=pd.DataFrame(shown).to_csv(index=False).encode("utf-8-sig"),file_name="smart_storage_event_logs.csv",mime="text/csv")
            counts=event_counts(events)
            popular=sorted(counts.items(),key=lambda item:item[1],reverse=True)[:8]
            fig3=plot_base(p,"Frekuensi kejadian pada event log yang terbaca",height=280)
            fig3.add_trace(go.Bar(x=[x[1] for x in popular[::-1]],y=[x[0] for x in popular[::-1]],orientation="h",marker_color=p["blue"]))
            st.plotly_chart(fig3,use_container_width=True,config={"displayModeBar":False})
        else:
            st.info("Belum ada event log untuk ditampilkan.")
    with tab_about:
        st.markdown("**Arsitektur:** DHT22 + LDR + sakelar pintu → ESP32 (Wokwi) → Firebase Realtime Database → Streamlit.")
        st.markdown("**Hak akses dashboard:** hanya operasi `GET /telemetry` dan `GET /event_logs`. Tidak ada pengendalian dari Streamlit ke Firebase maupun ESP32.")
        st.markdown("**Pin Wokwi:** DHT22 GPIO 4 · LDR GPIO 34 · pintu GPIO 32 · fault GPIO 33 · LED pendingin GPIO 26 · LED alarm GPIO 25 · buzzer GPIO 27.")
        st.markdown("**Ambang firmware terkini:** pendingin 24/22°C, alarm suhu 25/23°C, kelembapan 60/58%, alarm pintu 10 detik. Ini parameter simulasi, bukan standar penyimpanan fisik.")
        st.markdown("**Tentang status koneksi:** jika firmware belum mengirim `updated_at` berbasis waktu server, aplikasi menilai aktivitas dari perubahan `timestamp_ms` yang diamati. Snapshot pertama tidak membuktikan perangkat online.")
        st.markdown("**Demo Lokal:** data dihasilkan untuk ilustrasi; tidak ada request Firebase dalam mode ini.")

    st.markdown(f'<div class="ss-footer">© 2026 Kelompok 3 · Smart Medicine Storage Monitoring and Alarm Management System | Dibaca pada {escape(datetime.now().astimezone().strftime("%d %b %Y %H:%M:%S"))} (waktu server dashboard) · Read-only monitoring</div>',unsafe_allow_html=True)

render_dashboard()
