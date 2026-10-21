# Pengujian integrasi: Wokwi → Firebase → Streamlit → Wokwi

Catatan: tabel berikut adalah **rencana/panduan pengujian**, bukan hasil pengujian nyata. Ambil screenshot Firebase, Wokwi, Streamlit, dan Serial Monitor setelah menjalankan sendiri. Beri penanda SIMULATED untuk semua fault injection.

| ID | Tindakan di Wokwi/Streamlit | Harapan di Wokwi & Firebase | Harapan di Streamlit |
|---|---|---|---|
| U1 | DHT22 6°C; pintu ditutup; cahaya redup | NORMAL, cooler OFF, telemetry updated_at terus berganti | Online, suhu 6°C, cooler OFF |
| U2 | Ubah DHT 8.0°C lalu 7°C lalu 5.0°C | Cooler ON pada >=8, tetap ON di 7, OFF pada <=5 | Kurva suhu dan cooler_on aktual sinkron |
| U3 | DHT 12.0°C lalu 11°C lalu 10.0°C | TEMP_ALARM ON pada 12, tetap aktif di 11, OFF pada 10 | Status TEMP_ALARM dan log |
| U4 | Pintu dibuka <10 dtk, saat pendingin diminta ON | Cooler langsung OFF (interlock), tanpa DOOR_ALARM sebelum 10 dtk | door_open=true; cooler_on=false |
| U5 | Biarkan pintu terbuka >=10 dtk | DOOR_ALARM, door_violations+1, red LED/buzzer | Door alarm, event ALARM_DOOR |
| U6 | Mode MANUAL dari dashboard, tombol cooler ON saat pintu terbuka | CMD_REJECTED; cooler tetap OFF; tombol dashboard hanya mengirim intent apabila heartbeat aktif | Penolakan terlihat di event log |
| U7 | Mode MANUAL, pintu tertutup, LDR normal, tidak fault; ON/OFF | Actual cooler_on mengikuti command | Command dan actual sinkron ~3 detik |
| U8 | Ubah LDR terang saat pintu tertutup | LIGHT_ALARM dan cooler OFF | Indikator cahaya + alarm |
| U9 | Di Streamlit aktifkan inject_sensor_fault, atau Serial 's' | FAULT, cooler OFF; SENSOR_FAULT, event | Status alarm sensor dan data sensor tidak valid |
| U10 | Tekan tombol kuning di Wokwi (simulasi Firebase gagal) | Cloud fault, cooler OFF, log lokal queued; telemetry bisa menjadi STALE | Heartbeat STALE setelah ~16 detik; tekan lagi untuk pulih; event antre terkirim |
| U11 | Matikan Wokwi atau hentikan simulator | `updated_at` tidak diperbarui lagi | STALE, tombol ON dinonaktifkan |
| U12 | Tutup/buka Wokwi (reboot) | boot_id berubah, timestamp_ms reset | Chart sesi mulai ulang, log menunjukkan boot berbeda |

**Penting:** Wokwi tidak mensimulasikan penurunan suhu akibat pendingin; LED biru hanya representasi. Angka ambang adalah parameter latihan untuk cold storage, bukan standar keselamatan. 

Jangan menguji dengan aturan `.read: true` / `.write: true` di Firebase. Seluruh komunikasi harus memakai Firebase Authentication dan Security Rules berbasis UID.
