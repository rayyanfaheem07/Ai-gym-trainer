import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_profile_authenticated(authenticated_async_client: AsyncClient):
    response = await authenticated_async_client.get("/api/v1/profile")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["fitness_goal"] == "general_fitness"
    assert data["experience_level"] == "beginner"
    assert data["preferred_focus"] == "form"
    assert data["coaching_style"] == "supportive"


@pytest.mark.asyncio
async def test_update_profile_authenticated(authenticated_async_client: AsyncClient):
    update_payload = {
        "fitness_goal": "strength",
        "experience_level": "intermediate",
        "preferred_focus": "consistency",
        "coaching_style": "concise",
    }
    response = await authenticated_async_client.put("/api/v1/profile", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["fitness_goal"] == "strength"
    assert data["experience_level"] == "intermediate"
    assert data["preferred_focus"] == "consistency"
    assert data["coaching_style"] == "concise"

    # Follow-up GET
    get_res = await authenticated_async_client.get("/api/v1/profile")
    assert get_res.status_code == 200
    assert get_res.json()["fitness_goal"] == "strength"


@pytest.mark.asyncio
async def test_unauthenticated_profile_access_rejected(async_client: AsyncClient):
    get_res = await async_client.get("/api/v1/profile")
    assert get_res.status_code == 401

    put_res = await async_client.put("/api/v1/profile", json={"fitness_goal": "strength"})
    assert put_res.status_code == 401


@pytest.mark.asyncio
async def test_multi_tenant_profile_isolation(
    authenticated_async_client: AsyncClient,
    async_client: AsyncClient,
    second_auth_headers: dict[str, str],
):
    # User 1 sets goal to "strength"
    await authenticated_async_client.put(
        "/api/v1/profile",
        json={"fitness_goal": "strength", "coaching_style": "technical"},
    )

    # User 2 logs in with distinct JWT token
    user2_client = async_client
    get_user2 = await user2_client.get("/api/v1/profile", headers=second_auth_headers)
    assert get_user2.status_code == 200
    user2_data = get_user2.json()

    # User 2 must see their own default profile, NOT User 1's "strength" goal
    assert user2_data["fitness_goal"] == "general_fitness"
    assert user2_data["coaching_style"] == "supportive"

    # User 2 updates their profile to "fat_loss"
    await user2_client.put(
        "/api/v1/profile",
        json={"fitness_goal": "fat_loss"},
        headers=second_auth_headers,
    )

    # User 1 verifies their profile remains unchanged as "strength"
    get_user1 = await authenticated_async_client.get("/api/v1/profile")
    assert get_user1.json()["fitness_goal"] == "strength"
    assert get_user1.json()["coaching_style"] == "technical"
