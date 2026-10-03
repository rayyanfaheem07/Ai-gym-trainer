from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.rate_limit import rate_limit
from backend.app.models.user import User
from backend.app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from backend.app.services.auth_service import AuthService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user account with hashed password and normalized email.",
    dependencies=[Depends(rate_limit(settings.RATE_LIMIT_REGISTER_PER_MINUTE, 60.0))],
)
async def register(
    payload: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> User:
    service = AuthService(db)
    user = await service.register(payload)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticates credentials and returns a JWT Bearer access token.",
    dependencies=[Depends(rate_limit(settings.RATE_LIMIT_LOGIN_PER_MINUTE, 60.0))],
)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    service = AuthService(db)
    token, user = await service.authenticate(payload)
    return TokenResponse(
        access_token=token,
        token_type="bearer",  # nosec: B106
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the profile information of the currently authenticated user.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
