import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ai_engine_ready"] is True


@pytest.mark.asyncio
async def test_root_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ai_engine_ready"] is True


@pytest.mark.asyncio
async def test_documentation_redirects(async_client: AsyncClient):
    docs_resp = await async_client.get("/docs", follow_redirects=False)
    assert docs_resp.status_code in (307, 308)
    assert docs_resp.headers.get("location") == "/api/v1/docs"

    redoc_resp = await async_client.get("/redoc", follow_redirects=False)
    assert redoc_resp.status_code in (307, 308)
    assert redoc_resp.headers.get("location") == "/api/v1/redoc"
