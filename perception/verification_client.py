"""Thin HTTP client the perception pipeline uses to talk to `backend/`.

Built on `httpx` (already a project dependency) instead of `requests` so
the exact same client can be pointed at either a live server
(`base_url="http://localhost:8000"`) or, in tests, directly at the FastAPI
app in-process via `httpx.ASGITransport` -- no real network call or
subprocess needed to exercise this module's request/response handling.
"""
from __future__ import annotations

import httpx


class VerificationClientError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class VerificationClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        nurse_token: str = "",
        client: "httpx.Client | None" = None,
        timeout: float = 5.0,
    ):
        self.nurse_token = nurse_token
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "VerificationClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def _nurse_headers(self) -> dict:
        return {"x-nurse-token": self.nurse_token}

    def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            raise VerificationClientError(f"Request to {url} failed: {exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise VerificationClientError(
                f"{method} {url} -> {response.status_code}: {detail}",
                status_code=response.status_code,
            )
        return response.json()

    def get_state(self) -> dict:
        return self._request("GET", "/state")

    def get_request(self, request_id: str) -> dict:
        return self._request("GET", f"/requests/{request_id}")

    def verify(self, request_id: str, patient_id: str, kit_id: str) -> dict:
        return self._request(
            "POST",
            f"/tasks/{request_id}/verify",
            json={"patient_id": patient_id, "kit_id": kit_id},
            headers=self._nurse_headers(),
        )

    def transition(self, request_id: str, next_state: str) -> dict:
        return self._request(
            "POST",
            f"/tasks/{request_id}/transition",
            json={"next_state": next_state},
            headers=self._nurse_headers(),
        )
