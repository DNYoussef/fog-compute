import pytest
import httpx

from server.main import app


@pytest.mark.asyncio
async def test_orchestration_restart_requires_api_key():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/orchestration/restart/dao", json={})

    assert response.status_code == 401
    assert response.json()["detail"] == "API key required"


@pytest.mark.asyncio
async def test_orchestration_health_check_requires_api_key():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/orchestration/health/check-now")

    assert response.status_code == 401
    assert response.json()["detail"] == "API key required"


@pytest.mark.asyncio
async def test_bitchat_file_upload_init_requires_api_key():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/bitchat/files/upload",
            json={
                "filename": "payload.bin",
                "file_size": 4,
                "uploaded_by": "attacker",
                "mime_type": "application/octet-stream",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "API key required"


@pytest.mark.asyncio
async def test_bitchat_chunk_upload_requires_api_key():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/bitchat/files/file-1/chunks/0",
            files={"chunk_data": ("chunk.bin", b"test", "application/octet-stream")},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "API key required"
