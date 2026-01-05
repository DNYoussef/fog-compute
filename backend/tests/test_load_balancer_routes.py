"""
Tests for load balancer integration helpers.
"""
import httpx
import asyncio
import pytest
import sys
import types
import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
import importlib
from pathlib import Path

# Provide stub for optional dependency used by database engine initialization
if "aiosqlite" not in sys.modules:
    stub_aiosqlite = types.ModuleType("aiosqlite")
    stub_aiosqlite.Error = Exception
    stub_aiosqlite.Warning = Exception
    stub_aiosqlite.DatabaseError = Exception
    stub_aiosqlite.IntegrityError = Exception
    stub_aiosqlite.ProgrammingError = Exception
    stub_aiosqlite.OperationalError = Exception
    stub_aiosqlite.InterfaceError = Exception
    stub_aiosqlite.InternalError = Exception
    stub_aiosqlite.NotSupportedError = Exception
    stub_aiosqlite.DataError = Exception
    stub_aiosqlite.sqlite_version = "3.0.0"
    stub_aiosqlite.sqlite_version_info = (3, 0, 0)
    stub_aiosqlite.threadsafety = 1
    stub_aiosqlite.paramstyle = "qmark"
    stub_aiosqlite.apilevel = "2.0"
    stub_aiosqlite.Connection = object
    stub_aiosqlite.Cursor = object
    stub_aiosqlite.connect = lambda *args, **kwargs: None
    sys.modules["aiosqlite"] = stub_aiosqlite
else:
    stub_aiosqlite = sys.modules["aiosqlite"]

# Stub heavy SQLAlchemy components used during module import


def _fake_engine():
    class DummyEngine:
        async def dispose(self):
            return None

        async def begin(self):
            class DummyContext:
                async def __aenter__(self_inner):
                    return self_inner

                async def __aexit__(self_inner, exc_type, exc, tb):
                    return False

                async def run_sync(self_inner, fn):
                    return None

            return DummyContext()

    return DummyEngine()


def _fake_sessionmaker(*args, **kwargs):
    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def commit(self):
            return None

        async def rollback(self):
            return None

        async def close(self):
            return None

    def factory():
        return DummySession()

    return factory


sqlalchemy_asyncio.create_async_engine = lambda *args, **kwargs: _fake_engine()
sqlalchemy_asyncio.async_sessionmaker = _fake_sessionmaker

# Create lightweight package stubs to avoid importing full route registry
backend_root = Path(__file__).resolve().parent.parent
server_path = backend_root / "server"
routes_path = server_path / "routes"

if "server" not in sys.modules:
    server_pkg = types.ModuleType("server")
    server_pkg.__path__ = [str(server_path)]
    sys.modules["server"] = server_pkg

if "server.routes" not in sys.modules:
    routes_pkg = types.ModuleType("server.routes")
    routes_pkg.__path__ = [str(routes_path)]
    sys.modules["server.routes"] = routes_pkg

if "server.database" not in sys.modules:
    db_stub = types.ModuleType("server.database")

    async def _noop_db():
        yield None

    db_stub.get_db = _noop_db
    db_stub.get_db_context = _noop_db
    sys.modules["server.database"] = db_stub

deployment = importlib.import_module("server.routes.deployment")


class MockResponse:
    """Minimal async response mock supporting raise_for_status."""

    def __init__(self, status_code: int = 200, url: str = "http://lb"):
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", self.url)
            raise httpx.HTTPStatusError(
                "error",
                request=request,
                response=httpx.Response(self.status_code, request=request),
            )


class MockAsyncClient:
    """AsyncClient mock that records calls."""

    def __init__(self, status_code: int = 200, **kwargs):
        self.status_code = status_code
        self.kwargs = kwargs
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, params=None):
        self.requests.append({"method": "POST", "url": url, "json": json, "params": params})
        return MockResponse(status_code=self.status_code, url=url)

    async def delete(self, url, params=None):
        self.requests.append({"method": "DELETE", "url": url, "params": params})
        return MockResponse(status_code=self.status_code, url=url)


def test_update_load_balancer_routes_traefik_add(monkeypatch):
    """Ensure Traefik integration posts correct payload."""
    mock_client = MockAsyncClient()

    monkeypatch.setenv("LOAD_BALANCER_ENABLED", "true")
    monkeypatch.setenv("LOAD_BALANCER_TYPE", "traefik")
    monkeypatch.setenv("LOAD_BALANCER_API_URL", "http://lb")
    monkeypatch.setattr(deployment.httpx, "AsyncClient", lambda **kwargs: mock_client)

    result = asyncio.run(
        deployment._update_load_balancer_routes(
            "dep-123",
            action="add",
            endpoints=["http://node1:8080", "node2:8080"],
        )
    )

    assert result is True
    assert mock_client.requests[0]["url"] == "http://lb/api/http/services/dep-123"
    assert mock_client.requests[0]["json"]["loadBalancer"]["servers"] == [
        {"url": "http://node1:8080"},
        {"url": "http://node2:8080"},
    ]


def test_update_load_balancer_routes_nginx_remove(monkeypatch):
    """Ensure nginx removal hits upstream delete endpoint."""
    mock_client = MockAsyncClient()

    monkeypatch.setenv("LOAD_BALANCER_ENABLED", "true")
    monkeypatch.setenv("LOAD_BALANCER_TYPE", "nginx")
    monkeypatch.setenv("LOAD_BALANCER_API_URL", "http://nginx-plus")
    monkeypatch.setattr(deployment.httpx, "AsyncClient", lambda **kwargs: mock_client)

    result = asyncio.run(deployment._update_load_balancer_routes("dep-456", action="remove"))

    assert result is True
    assert mock_client.requests[0]["method"] == "DELETE"
    assert mock_client.requests[0]["url"] == "http://nginx-plus/api/6/http/upstreams/fog-dep-456/servers"
    assert mock_client.requests[0]["params"] == {"all": "true"}


def test_update_load_balancer_routes_haproxy_request_error(monkeypatch):
    """HAProxy errors should be handled gracefully."""

    class ErrorAsyncClient(MockAsyncClient):
        async def post(self, url, json=None, params=None):
            raise httpx.RequestError("connection failed", request=httpx.Request("POST", url))

    monkeypatch.setenv("LOAD_BALANCER_ENABLED", "true")
    monkeypatch.setenv("LOAD_BALANCER_TYPE", "haproxy")
    monkeypatch.setenv("LOAD_BALANCER_API_URL", "http://haproxy")
    monkeypatch.setattr(deployment.httpx, "AsyncClient", lambda **kwargs: ErrorAsyncClient())

    result = asyncio.run(
        deployment._update_load_balancer_routes(
            "dep-789", action="add", endpoints=["10.0.0.1:8080"]
        )
    )

    assert result is False
