import pytest

from ubuntu_mcp.exceptions import NetworkError, SecurityError, ValidationError
from ubuntu_mcp.tools import network


async def test_validate_url_accepts_http_https():
    result = await network.validate_url("https://example.com/path?x=1")
    assert result["valid"] is True
    assert result["hostname"] == "example.com"


async def test_validate_url_rejects_other_schemes():
    result = await network.validate_url("ftp://example.com/file")
    assert result["valid"] is False


async def test_parse_url():
    result = await network.parse_url("https://example.com:8080/a/b?x=1#frag")
    assert result == {
        "scheme": "https",
        "hostname": "example.com",
        "port": 8080,
        "path": "/a/b",
        "query": "x=1",
        "fragment": "frag",
    }


async def test_build_url_with_query():
    result = await network.build_url(
        "https://example.com/api", path="items", query={"limit": 5}
    )
    assert result["url"] == "https://example.com/api/items?limit=5"


async def test_build_url_rejects_non_http_scheme():
    with pytest.raises(ValidationError):
        await network.build_url("ftp://example.com")


async def test_fetch_url_rejects_bad_scheme():
    with pytest.raises(ValidationError):
        await network.fetch_url("file:///etc/passwd")


async def test_fetch_url_blocks_loopback():
    with pytest.raises(SecurityError):
        await network.fetch_url("http://127.0.0.1/secret")


async def test_check_connectivity_blocks_private_ip():
    with pytest.raises(SecurityError):
        await network.check_connectivity("192.168.1.1", 80)


async def test_check_connectivity_validates_port():
    with pytest.raises(ValidationError):
        await network.check_connectivity("example.com", 0)


class _FakeResponse:
    def __init__(self, status_code=200, body=b'{"ok": true}', url="https://example.com/"):
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}
        self.url = url
        self._body = body

    async def aiter_bytes(self):
        yield self._body


class _FakeStreamCM:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url):
        return _FakeStreamCM(_FakeResponse())


async def test_fetch_url_success(monkeypatch):
    monkeypatch.setattr(network.httpx, "AsyncClient", _FakeAsyncClient)
    result = await network.fetch_url("https://example.com/api")
    assert result["status_code"] == 200
    assert result["content"] == '{"ok": true}'


async def test_fetch_url_response_too_large(monkeypatch):
    from ubuntu_mcp.config import SETTINGS

    class _BigResponseClient(_FakeAsyncClient):
        def stream(self, method, url):
            return _FakeStreamCM(_FakeResponse(body=b"x" * 1000))

    monkeypatch.setattr(network.httpx, "AsyncClient", _BigResponseClient)
    original = SETTINGS.max_response_size
    object.__setattr__(SETTINGS, "max_response_size", 10)
    try:
        with pytest.raises(ValidationError):
            await network.fetch_url("https://example.com/big")
    finally:
        object.__setattr__(SETTINGS, "max_response_size", original)
