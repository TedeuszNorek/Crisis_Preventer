"""Shared HTTP client with retries and rate limiting."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """Simple rate limiter for API calls."""

    requests_per_minute: int = 60
    _timestamps: list[float] = field(default_factory=list, repr=False)

    def wait_if_needed(self) -> None:
        """Block if rate limit would be exceeded."""
        now = time.time()
        window_start = now - 60.0

        # Remove timestamps outside the window
        self._timestamps = [ts for ts in self._timestamps if ts > window_start]

        if len(self._timestamps) >= self.requests_per_minute:
            oldest = self._timestamps[0]
            wait_time = oldest - window_start
            if wait_time > 0:
                LOGGER.debug(f"Rate limit: waiting {wait_time:.2f}s")
                time.sleep(wait_time)

        self._timestamps.append(now)


class BaseClient:
    """Base HTTP client with retries and optional rate limiting.

    Subclass this for each data source.
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        api_key_param: Optional[str] = None,
        api_key_header: Optional[str] = None,
        timeout: int = 30,
        retries: int = 3,
        rate_limit: Optional[int] = None,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Base URL for the API.
            api_key: API key value.
            api_key_param: Query parameter name for API key (e.g., 'apiKey').
            api_key_header: Header name for API key (e.g., 'Authorization').
            timeout: Request timeout in seconds.
            retries: Number of retries for failed requests.
            rate_limit: Max requests per minute (None = no limit).
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_key_param = api_key_param
        self.api_key_header = api_key_header
        self.timeout = timeout

        self.session = requests.Session()
        retry_strategy = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.rate_limiter = RateLimiter(rate_limit) if rate_limit else None

    def _prepare_request(
        self,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> tuple[Dict[str, Any], Dict[str, str]]:
        """Add API key to params or headers as configured."""
        params = dict(params) if params else {}
        headers = dict(headers) if headers else {}

        if self.api_key:
            if self.api_key_param:
                params[self.api_key_param] = self.api_key
            if self.api_key_header:
                if self.api_key_header.lower() == "authorization":
                    headers["Authorization"] = f"Bearer {self.api_key}"
                else:
                    headers[self.api_key_header] = self.api_key

        return params, headers

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make a GET request.

        Args:
            path: URL path (appended to base_url).
            params: Query parameters.
            headers: HTTP headers.

        Returns:
            JSON response as dict.

        Raises:
            requests.HTTPError: If request fails.
        """
        if self.rate_limiter:
            self.rate_limiter.wait_if_needed()

        url = f"{self.base_url}{path}"
        params, headers = self._prepare_request(params, headers)

        LOGGER.debug(f"GET {url}")
        response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
        response.raise_for_status()

        return response.json()

    def post(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make a POST request.

        Args:
            path: URL path (appended to base_url).
            data: Form data.
            json_payload: JSON body.
            params: Query parameters.
            headers: HTTP headers.

        Returns:
            JSON response as dict.
        """
        if self.rate_limiter:
            self.rate_limiter.wait_if_needed()

        url = f"{self.base_url}{path}"
        params, headers = self._prepare_request(params, headers)

        LOGGER.debug(f"POST {url}")
        response = self.session.post(
            url, data=data, json=json_payload, params=params, headers=headers, timeout=self.timeout
        )
        response.raise_for_status()

        return response.json()

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self) -> "BaseClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
