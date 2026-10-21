# 🧊 Smart Storage Room — IoT Monitoring Dashboard

**Kelompok 3 · Internet of Things (ITO) · UTS 2026**

Dashboard monitoring ruang penyimpanan berbasis **Python + Streamlit** yang menampilkan data simulasi **ESP32 di Wokwi** melalui **Firebase Realtime Database**. Versi ini **100% read-only dari sisi dashboard**: pengguna dapat memantau kondisi ruangan, statistik, dan riwayat alarm, tetapi **tidak mengontrol Wokwi atau aktuator dari Streamlit**.

## ✨ Fitur

- 🌡️ Monitoring **suhu** dan **kelembapan** DHT22, **intensitas cahaya** LDR, dan **kondisi pintu**.
- 🧊 Indikator **status pendingin** (LED biru sebagai representasi), LED alarm, buzzer, dan *state machine* ESP32.
- 📊 Grafik suhu, kelembapan, dan cahaya yang merekam sampel **selama dashboard aktif**.
- 📋 **Event log** dari Firebase: jenis kejadian, deskripsi, uptime ESP32, dan filter/ekspor CSV.
- 🚦 Status aliran data: **menunggu pembaruan / mengalir / data lama / gagal membaca**.
- 🌓 Tema **Terang** dan **Gelap** serta tata letak responsif.
- 🔀 Sumber data **Demo Lokal** (simulasi tanpa Firebase) atau **Firebase Live** (pembacaan asli dari Firebase).
- 🔒 Akses Firebase RTDB **GET-only** untuk reader; tidak ada tombol kontrol atau permintaan database write dari Streamlit.

## 🧩 Arsitektur

```text
DHT22 / LDR / Sakelar Pintu
           │
           ▼
   ESP32 di Wokwi
  (state machine + interlock)
           │ HTTPS PUT/POST
           ▼
 Firebase Realtime Database
    ├─ /telemetry
    └─ /event_logs
           │ HTTPS GET + Firebase Anonymous Auth
           ▼
 Python + Streamlit Dashboard
     (MONITOR ONLY)
```

Dashboard tidak menggunakan path `/controls`; pengendalian perangkat tetap dilakukan secara lokal oleh Wokwi. Firebase dapat menyimpan `/controls` untuk kebutuhan firmware, tetapi dashboard tidak membaca maupun menulisnya.

## 🚀 Quick Start

1. Jalankan `python -m pip install -r requirements.txt`.
2. Jalankan `python -m streamlit run app.py`.
3. Pilih **Demo Lokal** untuk melihat fitur tanpa kredensial.
4. Untuk **Firebase Live**, aktifkan Anonymous Authentication dan isikan `.streamlit/secrets.toml` dari `.streamlit/secrets.toml.example`.
5. Jalankan Wokwi dan verifikasi pembaruan data di Firebase Console.

**Panduan lengkap (Windows, macOS/Linux, secrets, rules, Wokwi, GitHub, Streamlit Cloud):** [`docs/INSTALL_RUN_SECRETS.txt`](docs/INSTALL_RUN_SECRETS.txt).

## ☁️ Deploy via Streamlit Community Cloud

- Upload semua berkas proyek ke root repository GitHub (jangan unggah secrets asli).
- Buka [share.streamlit.io](https://share.streamlit.io/), pilih repository dan **main file `app.py`**.
- Pada pengaturan **Secrets**, masukkan TOML Firebase yang sama dengan konfigurasi lokal.
- Pilih **Demo Lokal** dulu untuk pengecekan UI, lalu **Firebase Live** saat data sudah mengalir.

## 📦 Struktur Repository

```text
.
├── app.py                         # Streamlit read-only dashboard
├── src/
│   ├── model.py                   # Normalisasi telemetri, event, status aliran
│   └── firebase_reader.py         # Firebase Auth token refresh + GET-only RTDB
├── data/demo_snapshot.json        # Sample data ekspor untuk demo lokal
├── firebase/
│   ├── rules.example.json         # Rules UID reader/device terpisah
│   └── controls.initial.json      # Inisialisasi opsional untuk firmware Wokwi
├── wokwi_reference/
│   ├── sketch.ino                  # Firmware kompatibilitas; terpisah dari dashboard
│   ├── diagram.json               # Wiring GPIO berdasarkan berkas kelompok
│   ├── libraries.txt
│   └── secrets.h.example          # Placeholder, tidak berisi kredensial
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example       # Contoh pengaturan, bukan secret asli
├── tools/create_anonymous_accounts.py
├── tests/
├── docs/INSTALL_RUN_SECRETS.txt
├── docs/STATUS_PENGUJIAN.md
├── requirements.txt
└── .gitignore
```

## 🔐 Keamanan & Firebase Anonymous Auth

Proyek ini **tidak memerlukan email/password**. Gunakan **dua akun anonim** melalui Firebase Authentication REST API: satu UID untuk perangkat Wokwi (*writer*) dan satu UID untuk Streamlit (*reader*). API Key Firebase **bukan izin baca database**; akun anonim mendapatkan ID token memakai refresh token yang disimpan sebagai rahasia pada lingkungan runtime.

Contoh Rules sudah memisahkan hak akses. **Jangan gunakan `.read: true` / `.write: true` agar aplikasi berjalan.** Jika memakai Wokwi asli yang belum mengautentikasi request (contoh `FIREBASE_AUTH=""`), firmware tersebut perlu diperbaiki terlebih dahulu agar dapat menulis pada Rules yang aman.

## 📊 Kontrak Data

Dashboard membaca **hanya**:

| Path | Data | Arah |
|---|---|---|
| `/telemetry` | suhu, RH, cahaya, pintu, state, pendingin, alarm, violation counters, uptime | Firebase → Streamlit |
| `/event_logs` | jenis kejadian, deskripsi, `timestamp_ms` (uptime), timestamp server jika ada | Firebase → Streamlit |

Sample ekspor proyek terbaru menggunakan `temperature`, `humidity`, `light_adc`, `light_pct`, `door_open`, `cooler_on`, `mode`, `state`, `door_violations`, `temp_violations`, dan `timestamp_ms`. **`timestamp_ms` menunjukkan waktu berjalan ESP32 sejak boot, bukan tanggal/waktu kalender.** Perbaikan firmware referensi menyediakan `updated_at` dari waktu server untuk verifikasi kesegaran data yang lebih kuat.

Kode Wokwi awal menimpa `/telemetry` secara berkala; karena itu aplikasi **tidak mengklaim memiliki riwayat historis** sebelum dashboard dibuka. Event log yang lama dapat berasal dari banyak sesi restart berbeda.

## 🧪 Pengujian

```bash
python -m pip install pytest
python -m pytest tests -q
```

Pengujian mengulas parsing ekspor database asli, alur login dan `GET` Firebase *mock*, status data lama, keamanan akses read-only, dan koneksi pin diagram. Tes tersebut **bukan bukti** bahwa jaringan Wokwi–Firebase–Streamlit telah diuji live; verifikasi aktual harus dilakukan oleh kelompok menggunakan proyek Firebase sendiri.

## 📝 Catatan akademik

DHT22, LDR, dan sakelar pintu merupakan input virtual Wokwi; LED biru menggambarkan pendingin, bukan pendinginan fisik. Ambang firmware yang dipakai contoh terbaru: pendingin **24/22°C**, alarm suhu **25/23°C**, kelembapan **60/58%**, alarm pintu **10 detik**. Nilai merupakan parameter latihan simulasi, bukan standar penyimpanan fisik.

**Anggota Kelompok 3:** Naail Safwan Saleh, Daniela Ivanka Maydina Siringoringo, Subhan, Adrian, Iqbal, dan Nayla.

## 📚 Referensi

- [Wokwi](https://wokwi.com/)
- [Streamlit](https://docs.streamlit.io/)
- [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud)
- [Firebase RTDB REST](https://firebase.google.com/docs/database/rest/start)
- [Firebase Anonymous Auth REST](https://firebase.google.com/docs/reference/rest/auth)
- [Firebase RTDB Security Rules](https://firebase.google.com/docs/database/security)
