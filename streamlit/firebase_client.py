"""Firebase Authentication and Realtime Database REST adapter for Streamlit.

No database secret or service-account key is required. The logged-in operator's
Firebase ID token is used, so Firebase Realtime Database Security Rules apply.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

import requests


class FirebaseError(RuntimeError):
    """A concise, non-secret error suitable for displaying in the UI."""


@dataclass
class AuthState:
    id_token: str
    refresh_token: str
    uid: str
    email: str
    expires_at: float


ALLOWED_CONTROLS = {"mode", "manual_cooler_req", "inject_sensor_fault"}


def validate_database_url(url: str) -> str:
    """Prevent credentials and REST requests being sent to arbitrary hosts."""
    value = (url or "").strip().rstrip("/")
    parts = urlsplit(value)
    hostname = (parts.hostname or "").lower()
    domain_ok = hostname.endswith(".firebaseio.com") or hostname.endswith(".firebasedatabase.app")
    if (parts.scheme != "https" or not domain_ok or parts.username or parts.password
            or parts.port or parts.path not in ("", "/") or parts.query or parts.fragment):
        raise FirebaseError("Database URL harus HTTPS dan berakhiran .firebaseio.com atau .firebasedatabase.app.")
    return value


class FirebaseClient:
    """Small REST client for a SINGLE device's shared Firebase project."""

    def __init__(self, database_url: str, api_key: str, session: requests.Session | None = None):
        self.database_url = validate_database_url(database_url)
        if not (api_key or "").strip():
            raise FirebaseError("Firebase Web API Key belum diatur di Streamlit Secrets.")
        self.api_key = api_key.strip()
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "SmartStorage-Kelompok3-Streamlit/1.0"})

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        try:
            response = self.session.request(method, url, timeout=(3.0, 6.0), **kwargs)
        except requests.RequestException as exc:
            raise FirebaseError("Firebase tidak dapat dijangkau (koneksi/timeout). Coba ulangi.") from exc
        if response.status_code >= 400:
            if response.status_code in (401, 403):
                message = "Akses ditolak (HTTP 401/403). Periksa login, token, dan Firebase Security Rules."
            elif response.status_code == 404:
                message = "Database tidak ditemukan (HTTP 404). Periksa Firebase Database URL."
            else:
                message = f"Permintaan Firebase gagal (HTTP {response.status_code})."
            raise FirebaseError(message)
        return response

    def sign_in(self, email: str, password: str) -> AuthState:
        """Email/password sign-in. Password is sent only to Firebase Auth over HTTPS."""
        if not email or not password:
            raise FirebaseError("Masukkan email dan password operator.")
        try:
            response = self._request(
                "POST", "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
                params={"key": self.api_key},
                json={"email": email, "password": password, "returnSecureToken": True},
            )
        except FirebaseError as exc:
            raise FirebaseError("Login Firebase gagal. Periksa email, password, API key, dan metode Email/Password.") from exc
        data = response.json()
        return AuthState(
            id_token=data["idToken"], refresh_token=data["refreshToken"],
            uid=data["localId"], email=data.get("email", email),
            expires_at=time.time() + max(1, int(data.get("expiresIn", 3600)) - 90),
        )

    def refresh(self, auth: AuthState) -> AuthState:
        response = self._request(
            "POST", "https://securetoken.googleapis.com/v1/token",
            params={"key": self.api_key},
            data={"grant_type": "refresh_token", "refresh_token": auth.refresh_token},
        )
        data = response.json()
        return AuthState(
            id_token=data["id_token"],
            refresh_token=data.get("refresh_token", auth.refresh_token),
            uid=data.get("user_id", auth.uid), email=auth.email,
            expires_at=time.time() + max(1, int(data.get("expires_in", 3600)) - 90),
        )

    def ensure_auth(self, auth: AuthState) -> AuthState:
        if time.time() >= auth.expires_at:
            return self.refresh(auth)
        return auth

    def _database(self, path: str, method: str, auth: AuthState,
                  value: Mapping[str, Any] | None = None,
                  params: Mapping[str, Any] | None = None) -> tuple[Any, AuthState]:
        if path not in ("telemetry", "controls", "event_logs"):
            raise ValueError("Path Firebase tidak diizinkan")
        fresh = self.ensure_auth(auth)
        query = {"auth": fresh.id_token}
        if params:
            query.update(params)
        response = self._request(method, f"{self.database_url}/{path}.json", params=query, json=value)
        try:
            return response.json(), fresh
        except ValueError as exc:
            raise FirebaseError("Respons Firebase tidak berformat JSON yang valid.") from exc

    def read_dashboard(self, auth: AuthState) -> tuple[dict, AuthState]:
        telemetry, auth = self._database("telemetry", "GET", auth)
        controls, auth = self._database("controls", "GET", auth)
        events, auth = self._database(
            "event_logs", "GET", auth,
            params={"orderBy": json.dumps("$key"), "limitToLast": 60},
        )
        return {"telemetry": telemetry, "controls": controls, "events": events}, auth

    def write_controls(self, auth: AuthState, change: Mapping[str, Any]) -> AuthState:
        """PATCH only explicitly supported command fields; never write actuator telemetry."""
        if not change or not set(change).issubset(ALLOWED_CONTROLS):
            raise ValueError("Field perintah tidak dikenal")
        if "mode" in change and change["mode"] not in ("AUTO", "MANUAL"):
            raise ValueError("Mode tidak valid")
        for name in ("manual_cooler_req", "inject_sensor_fault"):
            if name in change and type(change[name]) is not bool:
                raise ValueError(f"{name} harus true/false")
        _, updated = self._database("controls", "PATCH", auth, value=dict(change))
        return updated
