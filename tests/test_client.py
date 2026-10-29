"""Tests for ForgeFit HTTP client transport abstraction."""

from __future__ import annotations

import http.server
import threading
import time
import urllib.error
from unittest.mock import patch

import pytest

from forgefit.client import ResilienceClient


class MockResilienceHandler(http.server.BaseHTTPRequestHandler):
    """Local mock HTTP handler for testing client transport."""

    def log_message(self, format: str, *args: object) -> None:
        """Suppress standard HTTP server logging during tests."""
        return

    def do_GET(self) -> None:
        if self.path == "/200":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        elif self.path == "/404":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

        elif self.path == "/500":
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Internal Server Error")

        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/destination")
            self.end_headers()
            self.wfile.write(b"Redirecting")

        elif self.path == "/slow":
            # Sleep longer than client test timeout
            time.sleep(0.5)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"delayed")
        elif self.path == "/secret_error":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"private_key": "SUPER_SECRET_TOKEN_XYZ"}')

        elif self.path == "/large_body":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            self.wfile.write(b"X" * 65536)

        elif self.path == "/redirect_301":
            self.send_response(301)
            self.send_header("Location", "/destination")
            self.end_headers()

        elif self.path == "/redirect_307":
            self.send_response(307)
            self.send_header("Location", "/destination")
            self.end_headers()

        elif self.path == "/redirect_308":
            self.send_response(308)
            self.send_header("Location", "/destination")
            self.end_headers()

        else:
            self.send_response(400)
            self.end_headers()


@pytest.fixture(scope="module")
def mock_server() -> tuple[http.server.ThreadingHTTPServer, str]:
    """Start an isolated background loopback HTTP server for test duration."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockResilienceHandler)
    port = server.server_port
    base_url = f"http://127.0.0.1:{port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield server, base_url

    server.shutdown()
    server.server_close()


def test_client_http_200_success(
    mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """ResilienceClient correctly records HTTP 200 responses as successful."""
    _, base_url = mock_server
    client = ResilienceClient()

    resp = client.send_request(f"{base_url}/200", timeout_seconds=2.0)
    assert resp.status_code == 200
    assert resp.success is True
    assert resp.failure_category is None
    assert resp.error_message is None
    assert resp.latency_ms >= 0


def test_client_http_404_error(
    mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """ResilienceClient classifies 404 responses as http_error."""
    _, base_url = mock_server
    client = ResilienceClient()

    resp = client.send_request(f"{base_url}/404", timeout_seconds=2.0)
    assert resp.status_code == 404
    assert resp.success is False
    assert resp.failure_category == "http_error"
    assert "404" in (resp.error_message or "")


def test_client_http_500_error(
    mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """ResilienceClient distinguishes remote HTTP 500 from local simulated failures."""
    _, base_url = mock_server
    client = ResilienceClient()

    resp = client.send_request(f"{base_url}/500", timeout_seconds=2.0)
    assert resp.status_code == 500
    assert resp.success is False
    assert resp.failure_category == "http_error"
    assert "500" in (resp.error_message or "")


def test_client_does_not_follow_redirects(
    mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """ResilienceClient does not follow redirects, returning 302 directly."""
    _, base_url = mock_server
    client = ResilienceClient()

    resp = client.send_request(f"{base_url}/redirect", timeout_seconds=2.0)
    assert resp.status_code == 302
    assert resp.success is False
    assert resp.failure_category == "http_error"


def test_client_per_request_timeout(
    mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """ResilienceClient enforces per-request timeout and classifies as timeout."""
    _, base_url = mock_server
    client = ResilienceClient()

    # Request timeout is 0.1s, server delays for 0.5s
    resp = client.send_request(f"{base_url}/slow", timeout_seconds=0.1)
    assert resp.status_code is None
    assert resp.success is False
    assert resp.failure_category == "timeout"
    assert "timed out" in (resp.error_message or "").lower()


def test_client_connection_error() -> None:
    """ResilienceClient classifies connection failure as connection_error."""
    client = ResilienceClient()

    with patch.object(
        client._opener,
        "open",
        side_effect=urllib.error.URLError(ConnectionRefusedError("Connection refused")),
    ):
        resp = client.send_request(
            "http://127.0.0.1:8080/nonexistent", timeout_seconds=1.0
        )
        assert resp.status_code is None
        assert resp.success is False
        assert resp.failure_category == "connection_error"
        assert "connection" in (resp.error_message or "").lower()


def test_client_does_not_leak_response_body_on_http_error(
    mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """HTTP error responses do not leak sensitive response bodies into
    error messages.
    """
    _, base_url = mock_server
    client = ResilienceClient()

    resp = client.send_request(f"{base_url}/secret_error", timeout_seconds=2.0)
    assert resp.status_code == 500
    assert resp.success is False
    assert resp.failure_category == "http_error"
    # Verify the secret token inside the HTTP response body was never exposed
    assert "SUPER_SECRET_TOKEN_XYZ" not in (resp.error_message or "")
    assert "private_key" not in (resp.error_message or "")


def test_client_bounded_body_read_large_payload(
    mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """Client reads bounded response data without storing payload on response object."""
    _, base_url = mock_server
    client = ResilienceClient()

    resp = client.send_request(f"{base_url}/large_body", timeout_seconds=2.0)
    assert resp.status_code == 200
    assert resp.success is True
    assert resp.failure_category is None
    # ClientResponse has no body attribute, preventing memory exhaustion
    assert not hasattr(resp, "body")
    assert not hasattr(resp, "content")


def test_client_redirect_codes_301_307_308_not_followed(
    mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """All standard HTTP redirect codes (301, 307, 308) halt without following."""
    _, base_url = mock_server
    client = ResilienceClient()

    for path, expected_code in [
        ("/redirect_301", 301),
        ("/redirect_307", 307),
        ("/redirect_308", 308),
    ]:
        resp = client.send_request(f"{base_url}{path}", timeout_seconds=2.0)
        assert resp.status_code == expected_code
        assert resp.success is False
        assert resp.failure_category == "http_error"
