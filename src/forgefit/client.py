"""HTTP client transport abstraction for ForgeFit resilience testing."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom HTTP redirect handler that stops automatic redirect traversal.

    Prevents tests from silently following redirects to unapproved hosts.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        """Instruct urllib not to generate a redirect request."""
        return None

    def http_error_301(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any
    ) -> Any:
        return fp

    def http_error_302(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any
    ) -> Any:
        return fp

    def http_error_303(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any
    ) -> Any:
        return fp

    def http_error_307(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any
    ) -> Any:
        return fp

    def http_error_308(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any
    ) -> Any:
        return fp


@dataclass(slots=True)
class ClientResponse:
    """Internal result of an attempted HTTP request via ResilienceClient.

    Attributes:
        status_code: HTTP response status code, or None on network/timeout error.
        latency_ms: Monotonic duration of the request in milliseconds.
        success: Whether status code is within 2xx range (200-299).
        failure_category: 'http_error', 'timeout', 'connection_error', or None.
        error_message: Bounded, non-sensitive description of any error.
        start_time: Request dispatch timestamp (UTC).
        end_time: Request completion timestamp (UTC).
    """

    status_code: int | None
    latency_ms: float
    success: bool
    failure_category: str | None
    error_message: str | None
    start_time: datetime
    end_time: datetime


class ResilienceClient:
    """Minimal, controlled HTTP client for executing resilience probes.

    Enforces:
    - Non-redirecting behavior.
    - Explicit timeouts.
    - Monotonic duration measurement.
    - Bounded response body reading (max 4KB, discarded).
    - No credentials or sensitive headers by default.
    """

    def __init__(self, user_agent: str = "ForgeFit/1.0.0") -> None:
        self.user_agent = user_agent
        self._opener = urllib.request.build_opener(NoRedirectHandler)

    def send_request(
        self,
        target_url: str,
        timeout_seconds: float,
        method: str = "GET",
    ) -> ClientResponse:
        """Execute a single HTTP request with strict timeouts and error classification.

        Args:
            target_url: Validated HTTP/HTTPS URL.
            timeout_seconds: Timeout in seconds for socket connection and reading.
            method: HTTP method (defaults to GET).

        Returns:
            ClientResponse detailing status, latency, and failure classification.
        """
        request = urllib.request.Request(
            target_url,
            headers={"User-Agent": self.user_agent},
            method=method,
        )

        start_time = datetime.now(UTC)
        t_start = time.perf_counter()

        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                # Read at most 4KB of response body to verify complete transmission
                # without storing unbounded data or logging response bodies.
                try:
                    response.read(4096)
                except TimeoutError:
                    t_end = time.perf_counter()
                    end_time = datetime.now(UTC)
                    duration_ms = round((t_end - t_start) * 1000.0, 2)
                    return ClientResponse(
                        status_code=None,
                        latency_ms=duration_ms,
                        success=False,
                        failure_category="timeout",
                        error_message="Response read timed out",
                        start_time=start_time,
                        end_time=end_time,
                    )

                status_code = getattr(
                    response, "status", getattr(response, "code", 200)
                )
                t_end = time.perf_counter()
                end_time = datetime.now(UTC)
                duration_ms = round((t_end - t_start) * 1000.0, 2)

                # Classify 2xx as success; 3xx (non-followed redirect),
                # 4xx, and 5xx as non-success
                is_success = 200 <= status_code < 300
                category = None if is_success else "http_error"
                msg = None if is_success else f"HTTP {status_code}"

                return ClientResponse(
                    status_code=status_code,
                    latency_ms=duration_ms,
                    success=is_success,
                    failure_category=category,
                    error_message=msg,
                    start_time=start_time,
                    end_time=end_time,
                )

        except urllib.error.HTTPError as err:
            t_end = time.perf_counter()
            end_time = datetime.now(UTC)
            duration_ms = round((t_end - t_start) * 1000.0, 2)
            status_code = err.code
            is_success = 200 <= status_code < 300
            # Sanitize error: never read or expose response bodies or headers
            reason_str = str(getattr(err, "reason", "HTTP Error"))
            return ClientResponse(
                status_code=status_code,
                latency_ms=duration_ms,
                success=is_success,
                failure_category=None if is_success else "http_error",
                error_message=f"HTTP {status_code}: {reason_str}",
                start_time=start_time,
                end_time=end_time,
            )

        except urllib.error.URLError as err:
            t_end = time.perf_counter()
            end_time = datetime.now(UTC)
            duration_ms = round((t_end - t_start) * 1000.0, 2)

            # Distinguish timeout from connection refusal / network error
            reason = getattr(err, "reason", None)
            if isinstance(reason, TimeoutError) or (
                isinstance(reason, str) and "timed out" in reason.lower()
            ):
                return ClientResponse(
                    status_code=None,
                    latency_ms=duration_ms,
                    success=False,
                    failure_category="timeout",
                    error_message="Request timed out",
                    start_time=start_time,
                    end_time=end_time,
                )

            clean_reason = (
                type(reason).__name__
                if isinstance(reason, Exception)
                else str(reason)
                if reason
                else "Connection failed"
            )
            return ClientResponse(
                status_code=None,
                latency_ms=duration_ms,
                success=False,
                failure_category="connection_error",
                error_message=f"Connection failed: {clean_reason}",
                start_time=start_time,
                end_time=end_time,
            )

        except (ConnectionError, OSError) as err:
            t_end = time.perf_counter()
            end_time = datetime.now(UTC)
            duration_ms = round((t_end - t_start) * 1000.0, 2)
            if isinstance(err, TimeoutError) or "timed out" in str(err).lower():
                return ClientResponse(
                    status_code=None,
                    latency_ms=duration_ms,
                    success=False,
                    failure_category="timeout",
                    error_message="Request timed out",
                    start_time=start_time,
                    end_time=end_time,
                )
            return ClientResponse(
                status_code=None,
                latency_ms=duration_ms,
                success=False,
                failure_category="connection_error",
                error_message=f"Connection failed: {type(err).__name__}",
                start_time=start_time,
                end_time=end_time,
            )
