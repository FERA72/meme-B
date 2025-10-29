"""
Shared HTTP client utilities with retry/backoff logic and metrics recording.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlparse

import aiohttp
import requests
from aiohttp import ClientError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.metrics import METRICS

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504, 530}


class HttpError(RuntimeError):
    """Raised when an HTTP request ultimately fails after retries."""

    def __init__(self, message: str, status: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


@dataclass
class HttpResponse:
    status: int
    data: Any
    headers: Dict[str, str]


class HttpClient:
    """
    Wrapper around aiohttp / requests that adds retries, jittered backoff, and metrics.
    """

    def __init__(
        self,
        name: str,
        *,
        max_retries: int = 3,
        backoff_factor: float = 0.75,
        timeout: float = 10.0,
    ):
        self.name = name
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout

        # Default headers to avoid bot detection
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

        self._sync_session = requests.Session()
        self._sync_session.headers.update(self.default_headers)
        retry = Retry(
            total=max_retries,
            read=max_retries,
            connect=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=list(_RETRYABLE_STATUS),
            allowed_methods=frozenset({"GET", "POST", "PUT", "DELETE", "PATCH"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._sync_session.mount("http://", adapter)
        self._sync_session.mount("https://", adapter)

    # ------------------------------------------------------------------ #
    # Async helpers
    # ------------------------------------------------------------------ #
    async def _request_async(
        self,
        method: str,
        url: str,
        *,
        session: Optional[aiohttp.ClientSession] = None,
        expected_status: Iterable[int] = (200,),
        metrics_tag: Optional[str] = None,
        parse_json: bool = True,
        **kwargs,
    ) -> HttpResponse:
        """
        Execute an HTTP request with retries. If `session` is not provided a new
        ClientSession will be created for the lifetime of the call.
        """
        attempt = 0
        expected = set(expected_status)
        tag = metrics_tag or self._metric_tag(method, url)
        own_session = session is None

        # Merge default headers with user-provided headers
        merged_headers = dict(self.default_headers)
        if "headers" in kwargs:
            merged_headers.update(kwargs["headers"])
        kwargs["headers"] = merged_headers

        if own_session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            session = aiohttp.ClientSession(timeout=timeout, headers=self.default_headers)
        else:
            timeout = session.timeout if hasattr(session, "timeout") else aiohttp.ClientTimeout(total=self.timeout)

        try:
            while attempt < self.max_retries:
                attempt += 1
                start = time.perf_counter()
                try:
                    request_timeout = kwargs.pop("timeout", timeout)
                    async with session.request(method, url, timeout=request_timeout, **kwargs) as response:  # type: ignore[arg-type]
                        text = await response.text()
                        latency_ms = (time.perf_counter() - start) * 1000
                        status = response.status

                        if status in _RETRYABLE_STATUS and attempt < self.max_retries:
                            METRICS.record(tag, status, latency_ms, f"retryable_status:{status}")
                            await asyncio.sleep(self._sleep_interval(attempt))
                            continue

                        if status not in expected:
                            METRICS.record(tag, status, latency_ms, f"unexpected_status:{status}")
                            raise HttpError(f"Unexpected status {status} for {url}", status=status, payload=text)

                        data: Any
                        if parse_json:
                            try:
                                # Detect HTML responses (e.g., Cloudflare protection pages)
                                if text and text.strip().startswith(("<!DOCTYPE", "<html", "<!--")):
                                    METRICS.record(tag, status, latency_ms, "html_response_error")
                                    raise HttpError(
                                        f"Received HTML instead of JSON from {url} (possible bot protection)",
                                        status=status,
                                        payload=text[:500]
                                    )
                                data = json.loads(text) if text else {}
                            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                                METRICS.record(tag, status, latency_ms, "json_decode_error")
                                raise HttpError(f"Failed to decode JSON from {url}", status=status) from exc
                        else:
                            data = text

                        METRICS.record(tag, status, latency_ms)
                        return HttpResponse(status=status, data=data, headers=dict(response.headers))

                except (ClientError, asyncio.TimeoutError) as exc:
                    latency_ms = (time.perf_counter() - start) * 1000
                    if attempt >= self.max_retries:
                        METRICS.record(tag, None, latency_ms, err=str(exc))
                        raise HttpError(f"HTTP error for {url}: {exc}") from exc

                    METRICS.record(tag, None, latency_ms, err=f"retry:{exc}")
                    await asyncio.sleep(self._sleep_interval(attempt))

            raise HttpError(f"Failed to fetch {url} after retries")

        finally:
            if own_session and session:
                await session.close()

    async def get_json(
        self,
        url: str,
        *,
        session: Optional[aiohttp.ClientSession] = None,
        metrics_tag: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response = await self._request_async(
            "GET",
            url,
            session=session,
            metrics_tag=metrics_tag,
            headers=headers,
            params=params,
        )
        return response.data

    async def post_json(
        self,
        url: str,
        payload: Dict[str, Any],
        *,
        session: Optional[aiohttp.ClientSession] = None,
        metrics_tag: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        expected_status: Iterable[int] = (200,),
    ) -> Dict[str, Any]:
        headers = {**(headers or {}), "Content-Type": "application/json"}
        response = await self._request_async(
            "POST",
            url,
            session=session,
            metrics_tag=metrics_tag,
            json=payload,
            headers=headers,
            expected_status=expected_status,
        )
        return response.data

    # ------------------------------------------------------------------ #
    # Sync helpers
    # ------------------------------------------------------------------ #
    def request_sync(
        self,
        method: str,
        url: str,
        *,
        metrics_tag: Optional[str] = None,
        parse_json: bool = True,
        **kwargs,
    ) -> HttpResponse:
        tag = metrics_tag or self._metric_tag(method, url)
        start = time.perf_counter()

        try:
            response = self._sync_session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            METRICS.record(tag, None, latency_ms, err=str(exc))
            raise HttpError(f"HTTP error for {url}: {exc}") from exc

        latency_ms = (time.perf_counter() - start) * 1000
        status = response.status_code

        if status in _RETRYABLE_STATUS:
            METRICS.record(tag, status, latency_ms, f"retryable_status:{status}")
        elif 400 <= status:
            METRICS.record(tag, status, latency_ms, f"error_status:{status}")
        else:
            METRICS.record(tag, status, latency_ms)

        if parse_json:
            try:
                # Detect HTML responses (e.g., Cloudflare protection pages)
                text = response.text
                if text and text.strip().startswith(("<!DOCTYPE", "<html", "<!--")):
                    METRICS.record(tag, status, latency_ms, "html_response_error")
                    raise HttpError(
                        f"Received HTML instead of JSON from {url} (possible bot protection)",
                        status=status,
                        payload=text[:500]
                    )
                data = response.json()
            except ValueError as exc:
                raise HttpError(f"Failed to decode JSON from {url}", status=status) from exc
        else:
            data = response.text

        if status >= 400:
            raise HttpError(f"Unexpected status {status} for {url}", status=status, payload=data)

        return HttpResponse(status=status, data=data, headers=response.headers)  # type: ignore[arg-type]

    # ------------------------------------------------------------------ #
    def _sleep_interval(self, attempt: int) -> float:
        # Exponential backoff with jitter.
        base = self.backoff_factor * (2 ** (attempt - 1))
        return base + (base * 0.1)

    def _metric_tag(self, method: str, url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc or "unknown"
        path = parsed.path.rstrip("/") or "/"
        return f"{self.name}:{method}:{host}{path}"

