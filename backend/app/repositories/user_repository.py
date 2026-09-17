from backend.app.models.user import User
from backend.app.repositories.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.strip().lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password_hash: str,
        full_name: str | None = None,
    ) -> User:
        user = User(
            email=email.strip().lower(),
            password_hash=password_hash,
            full_name=full_name,
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_or_create(
        self,
        email: str,
        full_name: str | None = None,
        password_hash: str = "",
    ) -> User:
        user = await self.get_by_email(email)
        if user is None:
            user = await self.create_user(
                email=email,
                password_hash=password_hash,
                full_name=full_name,
            )
        return user
