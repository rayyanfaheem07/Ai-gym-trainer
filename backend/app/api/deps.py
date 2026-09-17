from backend.app.core.database import get_db
from backend.app.core.errors import AuthenticationError
from backend.app.core.security import decode_access_token
from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

security_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Bearer",
    description="JWT Bearer token authentication. Format: 'Bearer <token>'",
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that extracts, decodes, and validates the JWT Bearer token,
    then retrieves the authenticated User from the database.
    """
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication token is missing. Please provide a Bearer token.")

    token = credentials.credentials
    payload = decode_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token payload is missing user ID ('sub').")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if user is None:
        raise AuthenticationError("User associated with this token does not exist.")

    if not user.is_active:
        raise AuthenticationError("User account has been disabled.")

    return user
