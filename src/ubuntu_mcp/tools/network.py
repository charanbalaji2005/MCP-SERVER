"""Network tools: fetch_url, check_connectivity, resolve_dns, validate_url.

fetch_url enforces:
  - http/https schemes only
  - hostname must not resolve to a private/loopback/link-local address
    (see security.assert_public_host) -- blocks SSRF
  - request timeout
  - redirects capped
  - response body capped at MCP_MAX_RESPONSE_SIZE bytes
"""

from __future__ import annotations

import socket
from urllib.parse import urlencode, urlparse, urlunparse

import httpx

from ..config import SETTINGS
from ..exceptions import NetworkError, ValidationError
from ..security import assert_public_host, is_private_or_loopback

_ALLOWED_SCHEMES = {"http", "https"}


async def validate_url(url: str) -> dict:
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        return {"url": url, "valid": False, "reason": str(exc)}

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return {"url": url, "valid": False, "reason": "Only http/https schemes are allowed."}
    if not parsed.netloc:
        return {"url": url, "valid": False, "reason": "URL is missing a host."}

    return {
        "url": url,
        "valid": True,
        "scheme": parsed.scheme,
        "hostname": parsed.hostname,
        "port": parsed.port,
        "path": parsed.path or "/",
    }


async def parse_url(url: str) -> dict:
    parsed = urlparse(url)
    return {
        "scheme": parsed.scheme,
        "hostname": parsed.hostname,
        "port": parsed.port,
        "path": parsed.path,
        "query": parsed.query,
        "fragment": parsed.fragment,
    }


async def build_url(base_url: str, path: str = "", query: dict | None = None) -> dict:
    parsed = urlparse(base_url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValidationError("base_url must use http or https.")
    new_path = parsed.path.rstrip("/") + "/" + path.lstrip("/") if path else parsed.path
    query_string = urlencode(query) if query else parsed.query
    built = urlunparse(
        (parsed.scheme, parsed.netloc, new_path, "", query_string, "")
    )
    return {"url": built}


async def resolve_dns(hostname: str) -> dict:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise NetworkError(f"Could not resolve '{hostname}': {exc}") from exc

    addresses = sorted({info[4][0] for info in infos})
    return {
        "hostname": hostname,
        "addresses": addresses,
        "any_private": any(is_private_or_loopback(a) for a in addresses),
    }


async def check_connectivity(host: str, port: int, timeout: int = 3) -> dict:
    if not 1 <= port <= 65535:
        raise ValidationError("port must be between 1 and 65535.")
    assert_public_host(host)

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"host": host, "port": port, "reachable": True}
    except OSError as exc:
        return {"host": host, "port": port, "reachable": False, "reason": str(exc)}


async def fetch_url(url: str, timeout: int | None = None) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValidationError("Only http:// and https:// URLs are allowed.")
    if not parsed.hostname:
        raise ValidationError("URL is missing a hostname.")

    assert_public_host(parsed.hostname)

    effective_timeout = timeout or SETTINGS.http_timeout
    max_bytes = SETTINGS.max_response_size

    try:
        async with httpx.AsyncClient(
            timeout=effective_timeout, follow_redirects=True, max_redirects=5
        ) as client:
            async with client.stream("GET", url) as resp:
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValidationError(
                            f"Response exceeded the {max_bytes}-byte limit and was truncated."
                        )
                    chunks.append(chunk)
                body = b"".join(chunks)
                return {
                    "url": url,
                    "final_url": str(resp.url),
                    "status_code": resp.status_code,
                    "headers": dict(list(resp.headers.items())[:20]),
                    "content": body.decode(errors="replace"),
                    "truncated": False,
                }
    except httpx.TimeoutException as exc:
        raise NetworkError(f"Request to '{url}' timed out.") from exc
    except httpx.HTTPError as exc:
        raise NetworkError(f"Request to '{url}' failed: {exc}") from exc
