"""Low-level Sectors API client used by the UTCP registry.

Responsibilities (PRD 12):
* hold the base URL + API key (key read ONLY from config, never logged)
* timeout, retry with backoff for 429/5xx, NO retry for 400/404
* translate HTTP results into the uniform ToolResponse envelope
* detect "empty" payloads so the No-Data Gate can act correctly

The client intentionally knows nothing about agents; it is pure transport.
"""
from __future__ import annotations

import time

import requests

from config import config
from .envelope import ToolResponse, ok, empty, error


class SectorsClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 timeout: int | None = None, max_retry: int | None = None):
        # Allow override (used by tests, e.g. T20 "API key dimatikan").
        self._api_key = api_key if api_key is not None else config.SECTORS_API_KEY
        self.base_url = (base_url or config.SECTORS_BASE_URL).rstrip("/")
        self.timeout = timeout or config.TOOL_TIMEOUT_SECONDS
        self.max_retry = max_retry if max_retry is not None else config.TOOL_MAX_RETRY

    def _headers(self) -> dict:
        # Sectors expects the raw key in the Authorization header (no Bearer).
        return {"Authorization": self._api_key or ""}

    @staticmethod
    def _is_empty(data) -> bool:
        if data is None:
            return True
        if isinstance(data, (list, dict, str)) and len(data) == 0:
            return True
        return False

    def get(self, tool: str, path: str, args: dict, params: dict | None = None,
            data_extractor=None) -> ToolResponse:
        """Perform GET and wrap the result.

        ``args`` is the logical tool argument dict (for the evidence record).
        ``params`` is the actual query string sent to the API.
        ``data_extractor`` optionally pulls the meaningful payload out of the
        raw JSON (e.g. a specific section) and may return None to signal empty.
        """
        if not self._api_key:
            return error(tool, args, None, "API key tidak tersedia (SECTORS_API_KEY kosong)")

        url = f"{self.base_url}/{path.lstrip('/')}"
        attempt = 0
        last_reason = "unknown"
        while attempt <= self.max_retry:
            try:
                resp = requests.get(url, headers=self._headers(), params=params or {},
                                    timeout=self.timeout)
            except requests.Timeout:
                last_reason = "timeout"
                attempt += 1
                time.sleep(min(2 ** attempt, 8))
                continue
            except requests.RequestException as e:
                return error(tool, args, None, f"request error: {type(e).__name__}")

            code = resp.status_code

            if code == 200:
                try:
                    raw = resp.json()
                except ValueError:
                    return error(tool, args, 200, "respons bukan JSON valid")
                data = data_extractor(raw) if data_extractor else raw
                if self._is_empty(data):
                    return empty(tool, args, http_status=200, reason="payload kosong")
                return ok(tool, args, data, http_status=200)

            if code in (400, 404):
                # Do not retry client errors (invalid param / symbol not found).
                reason = self._error_message(resp) or f"HTTP {code}"
                return error(tool, args, code, reason)

            if code == 429 or 500 <= code < 600:
                last_reason = f"HTTP {code}"
                attempt += 1
                time.sleep(min(2 ** attempt, 8))
                continue

            return error(tool, args, code, self._error_message(resp) or f"HTTP {code}")

        return error(tool, args, None, f"gagal setelah retry: {last_reason}")

    @staticmethod
    def _error_message(resp) -> str | None:
        try:
            body = resp.json()
        except ValueError:
            return None
        if isinstance(body, dict):
            return body.get("error") or body.get("message") or body.get("details")
        return None
