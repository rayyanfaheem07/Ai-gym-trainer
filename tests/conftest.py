import asyncio
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base, get_db
from backend.app.core.security import create_access_token, hash_password
from backend.app.main import create_application
from backend.app.models.user import User

# Test in-memory SQLite database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Creates a standard active test user in the test database."""
    user = User(
        email="athlete@example.com",
        password_hash=hash_password("StrongP@ssw0rd!"),
        full_name="Test Athlete",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


@pytest.fixture(scope="function")
async def second_user(db_session: AsyncSession) -> User:
    """Creates a second distinct user for multi-tenant isolation testing."""
    user = User(
        email="challenger@example.com",
        password_hash=hash_password("ChallengerP@ss123"),
        full_name="Challenger Athlete",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


@pytest.fixture(scope="function")
def auth_headers(test_user: User) -> dict[str, str]:
    """Returns Bearer Authorization headers for the primary test user."""
    token = create_access_token(subject=test_user.id, email=test_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def second_auth_headers(second_user: User) -> dict[str, str]:
    """Returns Bearer Authorization headers for the second user."""
    token = create_access_token(subject=second_user.id, email=second_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_application()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="function")
async def authenticated_async_client(
    db_session: AsyncSession,
    auth_headers: dict[str, str],
) -> AsyncGenerator[AsyncClient, None]:
    """Client pre-configured with Bearer auth token for the primary test user."""
    app = create_application()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        yield client

