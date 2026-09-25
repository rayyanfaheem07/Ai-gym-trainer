from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.profile import UserProfileResponse, UserProfileUpdate
from backend.app.services.personalization_service import PersonalizationService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user's fitness profile",
    description="Retrieves the personalization preferences, experience level, fitness goals, and coaching style for the authenticated athlete.",
)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Retrieve personal fitness profile for the authenticated user."""
    return await PersonalizationService.get_profile(db, user_id=current_user.id)


@router.put(
    "",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update authenticated user's fitness profile",
    description="Updates personalization preferences, experience level, fitness goals, and coaching style for the authenticated athlete.",
)
async def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Update personal fitness profile for the authenticated user."""
    return await PersonalizationService.update_profile(
        db,
        user_id=current_user.id,
        update_data=payload,
    )
