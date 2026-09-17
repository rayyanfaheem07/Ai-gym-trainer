from backend.app.core.errors import AuthenticationError, DuplicateEntityError
from backend.app.core.security import create_access_token, hash_password, verify_password
from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.auth import UserLogin, UserRegister
from sqlalchemy.ext.asyncio import AsyncSession


class AuthService:
    """Service handling user registration, authentication, and token generation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def register(self, payload: UserRegister) -> User:
        """
        Registers a new user account with validated credentials and hashed password.
        """
        existing = await self.user_repo.get_by_email(payload.email)
        if existing:
            raise DuplicateEntityError(
                entity_name="User",
                field_name="email",
                field_value=payload.email,
            )

        hashed = hash_password(payload.password)
        user = await self.user_repo.create_user(
            email=payload.email,
            password_hash=hashed,
            full_name=payload.full_name,
        )
        return user

    async def authenticate(self, payload: UserLogin) -> tuple[str, User]:
        """
        Validates user credentials and issues an access token.
        Returns a tuple of (access_token, User).
        """
        user = await self.user_repo.get_by_email(payload.email)
        if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
            raise AuthenticationError("Incorrect email or password.")

        if not user.is_active:
            raise AuthenticationError("Account is inactive. Please contact support.")

        token = create_access_token(subject=user.id, email=user.email)
        return token, user
