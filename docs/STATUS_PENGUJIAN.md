# Status Verifikasi Proyek

**Ruang lingkup:** Streamlit dashboard read-only dan kompatibilitas data yang dilampirkan.

| Komponen | Status | Keterangan |
|---|---|---|
| Pembacaan ekspor Firebase terbaru | LULUS lokal | Field telemetry dan 28 event legacy dapat dibaca |
| Validasi data kosong/sensor tidak valid | LULUS lokal | `-999`, `nan`, dan field opsional tidak merusak fungsi normalisasi |
| Firebase REST GET dan refresh anonim | LULUS mock | Memakai respons HTTP simulasi, **bukan** jaringan Firebase nyata |
| Pembatasan operasi ke GET telemetry dan event_logs | LULUS code/test | Tidak ada PUT/PATCH/DELETE di modul pembaca |
| Akses kontrol dari dashboard | TIDAK ADA | Tidak ada tombol atau operasi `/controls` dari Streamlit |
| Syntax Python | LULUS | `compileall` |
| Berkas JSON & pin Wokwi | LULUS lokal | Diagram tervalidasi, mapping sesuai user |
| Render jalur demo menggunakan Streamlit mock | LULUS smoke mock | `app.py` dieksekusi dengan substitusi komponen API Streamlit; bukan render browser |
| Rendering UI pada runtime Streamlit asli | BELUM TERVERIFIKASI | Instalasi Streamlit gagal karena DNS/jaringan pengujian tidak tersedia |
| Kompilasi firmware referensi di Wokwi | BELUM TERVERIFIKASI | Tidak ada simulasi/browser Wokwi dalam pengujian lokal |
| Real-time Firebase project kelompok | BELUM TERVERIFIKASI | Kredensial dan koneksi project asli tidak tersedia |
| Deploy GitHub / Streamlit Community Cloud | BELUM DILAKUKAN | Perlu upload dan secrets oleh pemilik repository |

**Batasan sumber data:** `/telemetry` di-overwrite; grafik hanya riwayat observasi selama halaman aktif. Event log contoh tidak memiliki timestamp kalender, hanya uptime ESP32. Status awal tidak mengklaim ONLINE sampai aliran data berubah atau timestamp server masih segar.
