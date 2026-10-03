"""Anthropic-compatible proxy: forwards /v1/* to the real API using the owner's
key, counting usage per account on the way through."""

from __future__ import annotations

import json
from typing import AsyncIterator, Callable, Optional

import httpx

from . import config

# Header forwarding: request/response headers the Anthropic SDK cares about.
_FORWARD_REQUEST = (
    "anthropic-version", "anthropic-beta", "content-type", "accept", "user-agent",
)
_FORWARD_RESPONSE = ("content-type", "request-id", "anthropic-ratelimit-requests-remaining")

_TIMEOUT = httpx.Timeout(30.0, read=900.0, write=120.0, pool=30.0)


def new_client() -> httpx.AsyncClient:
    """Tests monkeypatch this to inject a mock transport."""
    return httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False)


def upstream_headers(extra: dict) -> dict:
    headers = {k: v for k, v in extra.items() if k.lower() in _FORWARD_REQUEST}
    headers["x-api-key"] = config.ANTHROPIC_API_KEY
    return headers


def filter_response_headers(headers: httpx.Headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() in _FORWARD_RESPONSE}


def parse_usage_json(payload: bytes) -> tuple[int, int]:
    try:
        usage = json.loads(payload).get("usage") or {}
        return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    except (ValueError, AttributeError, TypeError):
        return 0, 0


class _StreamUsageScanner:
    """Best-effort SSE scan: pulls input/output token counts out of
    message_start / message_delta events without buffering the whole stream."""

    def __init__(self) -> None:
        self._buf = b""
        self.input_tokens = 0
        self.output_tokens = 0

    def feed(self, chunk: bytes) -> None:
        self._buf += chunk
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            self._parse_line(line.strip())

    def _parse_line(self, line: bytes) -> None:
        if not line.startswith(b"data:"):
            return
        try:
            event = json.loads(line[5:].strip())
        except ValueError:
            return
        usage = event.get("usage") or (event.get("message") or {}).get("usage") or {}
        if "input_tokens" in usage:
            self.input_tokens = max(self.input_tokens, int(usage["input_tokens"] or 0))
        if "output_tokens" in usage:
            self.output_tokens = max(self.output_tokens, int(usage["output_tokens"] or 0))


async def forward_json(method: str, path: str, body: Optional[dict],
                       request_headers: dict) -> tuple[int, bytes, dict]:
    """Non-streaming pass-through. Returns (status, body, response_headers)."""
    client = new_client()
    try:
        resp = await client.request(
            method, f"{config.UPSTREAM_BASE_URL}{path}",
            json=body, headers=upstream_headers(request_headers),
        )
        return resp.status_code, resp.content, filter_response_headers(resp.headers)
    finally:
        await client.aclose()


async def forward_stream(path: str, body: dict, request_headers: dict,
                         on_usage: Callable[[int, int], None]) -> tuple[
        int, Optional[AsyncIterator[bytes]], dict, Optional[bytes]]:
    """Streaming pass-through for /v1/messages with stream=true.

    Opens the upstream connection first so auth errors surface as normal HTTP
    statuses. Returns (status, body_iterator|None, headers, error_body|None).
    """
    client = new_client()
    request = client.build_request(
        "POST", f"{config.UPSTREAM_BASE_URL}{path}",
        json=body, headers=upstream_headers(request_headers),
    )
    try:
        resp = await client.send(request, stream=True)
    except httpx.HTTPError:
        await client.aclose()
        raise

    if resp.status_code != 200:
        error_body = await resp.aread()
        await resp.aclose()
        await client.aclose()
        return resp.status_code, None, filter_response_headers(resp.headers), error_body

    scanner = _StreamUsageScanner()

    async def body_iter() -> AsyncIterator[bytes]:
        try:
            async for chunk in resp.aiter_bytes():
                scanner.feed(chunk)
                yield chunk
        finally:
            on_usage(scanner.input_tokens, scanner.output_tokens)
            await resp.aclose()
            await client.aclose()

    return resp.status_code, body_iter(), filter_response_headers(resp.headers), None
