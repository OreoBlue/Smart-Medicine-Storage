"""Local bootstrap helper. Prints credentials to terminal; NEVER commit the output."""
import getpass
import requests

key=getpass.getpass("Firebase WEB API key (input tersembunyi): ").strip()
if not key:
    raise SystemExit("API key kosong")
print("Mengaktifkan Anonymous provider di Firebase Console terlebih dulu wajib.")
for role in ("WOKWI_DEVICE", "STREAMLIT_READER"):
    result=requests.post("https://identitytoolkit.googleapis.com/v1/accounts:signUp",params={"key":key},json={"returnSecureToken":True},timeout=15)
    if result.status_code!=200:
        raise SystemExit(f"Gagal membuat {role}: HTTP {result.status_code} (cek Anonymous provider/API key)")
    data=result.json()
    print(f"\n[{role}]  — RAHASIA, JANGAN DIPUBLIKASIKAN")
    print("UID:",data["localId"])
    print("REFRESH TOKEN:",data["refreshToken"])
print("\nSimpan UID di Firebase Rules; refresh token di secrets masing-masing, jangan di GitHub.")
