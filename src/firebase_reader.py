"""Read-only Firebase RTDB adapter. Auth refresh uses POST to Google Identity service only."""
from __future__ import annotations
import time
import requests

class FirebaseReadError(RuntimeError):
    pass

class FirebaseReader:
    def __init__(self, database_url: str, api_key: str, refresh_token: str, *, session=None, clock=None):
        self.url = str(database_url).rstrip("/")
        if not self.url.startswith("https://") or not self.url.endswith(("firebaseio.com", "firebasedatabase.app")):
            raise ValueError("URL Firebase harus https://...firebaseio.com atau ...firebasedatabase.app")
        self.api_key = api_key
        self.refresh_token = refresh_token
        if not api_key or not refresh_token:
            raise ValueError("api_key dan refresh_token anonim wajib diisi")
        self.session = session if session is not None else requests.Session()
        self.clock = clock or time.time
        self.id_token = ""
        self.expires_at = 0.0

    def _authenticate(self):
        endpoint = "https://securetoken.googleapis.com/v1/token"
        try:
            response = self.session.post(endpoint, params={"key": self.api_key},
                data={"grant_type": "refresh_token", "refresh_token": self.refresh_token}, timeout=10)
        except requests.RequestException as exc:
            raise FirebaseReadError("Gagal menghubungi Firebase Authentication. Cek jaringan.") from None
        if response.status_code != 200:
            raise FirebaseReadError(f"Firebase Authentication gagal (HTTP {response.status_code}). Cek refresh token atau API key.")
        try:
            data = response.json()
            self.id_token = data["id_token"]
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            self.expires_at = self.clock() + max(60, int(data.get("expires_in", 3600)) - 90)
        except (KeyError, TypeError, ValueError) as exc:
            raise FirebaseReadError("Respons token Firebase tidak sesuai format.") from None

    def read(self, path: str, *, params: dict | None = None):
        if path not in ("telemetry", "event_logs"):
            raise ValueError("Dashboard monitoring hanya boleh membaca /telemetry dan /event_logs")
        if not self.id_token or self.clock() >= self.expires_at:
            self._authenticate()
        request_params = dict(params or {})
        request_params["auth"] = self.id_token
        try:
            response = self.session.get(f"{self.url}/{path}.json", params=request_params, timeout=10)
        except requests.RequestException:
            raise FirebaseReadError("Tidak dapat membaca Firebase. Periksa jaringan dan Database URL.") from None
        if response.status_code == 401:
            self.id_token = "" # force refresh on next attempt
            raise FirebaseReadError("HTTP 401: token ditolak atau kedaluwarsa.")
        if response.status_code == 403:
            raise FirebaseReadError("HTTP 403: Security Rules tidak mengizinkan UID operator membaca path ini.")
        if response.status_code != 200:
            raise FirebaseReadError(f"Firebase gagal membaca {path} (HTTP {response.status_code}).")
        try:
            return response.json()
        except ValueError:
            raise FirebaseReadError(f"Respons {path} bukan JSON yang valid.") from None

    def fetch(self):
        telemetry = self.read("telemetry")
        events = self.read("event_logs", params={"orderBy": '"$key"', "limitToLast": 120})
        return telemetry, events
