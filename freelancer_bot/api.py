"""httpx-based async API client for Freelancer.com API v0.1.

Features:
- Async HTTP with httpx session reuse
- Exponential backoff retry (1s, 2s, 4s, 8s, 16s)
- Rate limiting awareness (respect Retry-After headers)
- Proper error handling with typed exceptions
- OAuth token auth via FREELANCER_OAUTH_TOKEN env var
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

API_BASE = "https://www.freelancer.com/api"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 5
BASE_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 32.0
JITTER = 0.1  # ±10% jitter


class FreelancerAPIError(Exception):
    """Base exception for API errors."""


class AuthenticationError(FreelancerAPIError):
    """401 — invalid/expired token."""


class RateLimitError(FreelancerAPIError):
    """429 — rate limited."""


class ServerError(FreelancerAPIError):
    """5xx — server-side error."""


class NotFoundError(FreelancerAPIError):
    """404 — resource not found."""


class BadRequestError(FreelancerAPIError):
    """400 — bad request."""


@dataclass
class APIClient:
    """Async Freelancer.com API client with retry, backoff, and rate limiting."""

    token: str = field(default_factory=lambda: os.environ.get("FREELANCER_OAUTH_TOKEN", ""))
    user_id: int = 32666915
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = MAX_RETRIES
    _client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)
    _rate_limit_until: float = field(default=0.0, init=False, repr=False)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("APIClient not initialized — use async with or call ainit()")
        return self._client

    async def ainit(self) -> None:
        """Initialize the httpx client (call before use if not using async context manager)."""
        if self._client is not None:
            return
        self._client = httpx.AsyncClient(
            base_url=API_BASE,
            timeout=httpx.Timeout(self.timeout),
            headers=self._default_headers(),
        )

    async def aclose(self) -> None:
        """Close the httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "APIClient":
        await self.ainit()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    def _default_headers(self) -> dict[str, str]:
        return {
            "freelancer-oauth-v1": self.token,
            "Accept": "application/json",
            "User-Agent": f"FreelancerBot/2.0 (user:{self.user_id})",
        }

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        delay = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
        jitter = delay * JITTER * (2 * random.random() - 1)  # ±10%
        return delay + jitter

    async def _handle_rate_limit(self, response: httpx.Response) -> None:
        """Handle 429 rate limit — wait for Retry-After or default 60s."""
        retry_after = response.headers.get("Retry-After", "60")
        try:
            wait = float(retry_after)
        except ValueError:
            wait = 60.0
        self._rate_limit_until = time.monotonic() + wait
        logger.warning("rate_limited", wait_seconds=wait)
        await asyncio.sleep(wait)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with retry/backoff logic."""
        if self._client is None:
            await self.ainit()

        # Respect rate limit cooldown
        remaining = self._rate_limit_until - time.monotonic()
        if remaining > 0:
            logger.debug("rate_limit_cooldown", remaining=remaining)
            await asyncio.sleep(remaining)

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json,
                )

                if response.status_code == 429:
                    await self._handle_rate_limit(response)
                    continue  # retry after waiting

                if response.status_code == 401:
                    raise AuthenticationError(
                        f"Authentication failed (401). Check FREELANCER_OAUTH_TOKEN. "
                        f"Response: {response.text[:500]}"
                    )

                if response.status_code == 404:
                    raise NotFoundError(f"Resource not found: {path}")

                if response.status_code == 400:
                    raise BadRequestError(
                        f"Bad request to {path}: {response.text[:500]}"
                    )

                if response.status_code >= 500:
                    raise ServerError(
                        f"Server error {response.status_code} from {path}: {response.text[:500]}"
                    )

                # Success (2xx, 3xx)
                return response

            except (AuthenticationError, NotFoundError, BadRequestError):
                raise  # don't retry client errors (except 429)

            except (httpx.TimeoutException, httpx.NetworkError, ServerError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "request_retry",
                        method=method,
                        path=path,
                        attempt=attempt + 1,
                        delay=round(delay, 2),
                        error=str(e)[:200],
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "request_exhausted_retries",
                        method=method,
                        path=path,
                        attempts=self.max_retries + 1,
                    )

            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "http_status_retry",
                        status=e.response.status_code,
                        attempt=attempt + 1,
                        delay=round(delay, 2),
                    )
                    await asyncio.sleep(delay)
                else:
                    raise FreelancerAPIError(
                        f"HTTP {e.response.status_code} from {path}: {e.response.text[:500]}"
                    ) from e

        raise FreelancerAPIError(
            f"Request failed after {self.max_retries + 1} attempts: {last_exception}"
        ) from last_exception

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET request returning parsed JSON."""
        response = await self._request("GET", path, params=params)
        return response.json()

    async def post(
        self, path: str, *, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """POST request returning parsed JSON."""
        response = await self._request("POST", path, params=params, json=json)
        return response.json()

    # ── Convenience methods ──────────────────────────────────────────────

    async def get_self(self) -> dict[str, Any]:
        """Get current user info."""
        return await self.get("/users/0.1/self/")

    async def search_projects(
        self,
        query: str,
        *,
        project_types: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        compact: bool = True,
    ) -> dict[str, Any]:
        """Search active projects."""
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "offset": offset,
        }
        if project_types:
            for pt in project_types:
                params.setdefault("project_types[]", []).append(pt)  # type: ignore[index]
        if compact:
            params["compact"] = ""
        return await self.get("/projects/0.1/projects/active/", params=params)

    async def get_project(self, project_id: int) -> dict[str, Any]:
        """Get full project details."""
        return await self.get(f"/projects/0.1/projects/{project_id}/")

    async def place_bid(
        self,
        project_id: int,
        amount: float,
        period: int,
        description: str,
        *,
        milestone_percentage: int = 100,
    ) -> dict[str, Any]:
        """Place a bid on a project."""
        payload = {
            "project_id": project_id,
            "amount": amount,
            "period": period,
            "description": description,
            "milestone_percentage": milestone_percentage,
        }
        return await self.post("/projects/0.1/bids/", params={"compact": ""}, json=payload)

    async def search_contests(
        self,
        query: str,
        *,
        limit: int = 50,
        offset: int = 0,
        sort_field: str = "time_submitted",
        reverse_sort: bool = True,
        compact: bool = True,
    ) -> dict[str, Any]:
        """Search active contests."""
        params: dict[str, Any] = {
            "query": query,
            "statuses[]": ["active"],
            "limit": limit,
            "offset": offset,
            "sort_field": sort_field,
            "reverse_sort": str(reverse_sort).lower(),
        }
        if compact:
            params["compact"] = ""
        return await self.get("/contests/0.1/contests/", params=params)

    async def get_contest(self, contest_id: int) -> dict[str, Any]:
        """Get full contest details."""
        return await self.get(f"/contests/0.1/contests/{contest_id}/")

    async def enter_contest(
        self, contest_id: int, entry_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Submit an entry to a contest."""
        return await self.post(
            f"/contests/0.1/contests/{contest_id}/entries/",
            json=entry_data,
        )
