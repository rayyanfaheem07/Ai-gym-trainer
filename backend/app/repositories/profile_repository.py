from backend.app.models.user_profile import (
    CoachingStyle,
    ExperienceLevel,
    FitnessGoal,
    PreferredFocus,
    UserProfile,
)
from backend.app.repositories.base import BaseRepository
from backend.app.schemas.profile import UserProfileUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ProfileRepository(BaseRepository[UserProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(UserProfile, session)

    async def get_by_user_id(self, user_id: str) -> UserProfile | None:
        """Fetch user profile by user_id."""
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: str) -> UserProfile:
        """Fetch user profile or create default profile if not exists."""
        profile = await self.get_by_user_id(user_id)
        if profile is None:
            profile = UserProfile(
                user_id=user_id,
                fitness_goal=FitnessGoal.GENERAL_FITNESS,
                experience_level=ExperienceLevel.BEGINNER,
                preferred_focus=PreferredFocus.FORM,
                coaching_style=CoachingStyle.SUPPORTIVE,
            )
            self.session.add(profile)
            await self.session.flush()
        return profile

    async def update_profile(
        self,
        user_id: str,
        update_data: UserProfileUpdate,
    ) -> UserProfile:
        """Update existing user profile or create one with updated fields."""
        profile = await self.get_or_create(user_id)

        if update_data.fitness_goal is not None:
            profile.fitness_goal = FitnessGoal(update_data.fitness_goal.value)
        if update_data.experience_level is not None:
            profile.experience_level = ExperienceLevel(update_data.experience_level.value)
        if update_data.preferred_focus is not None:
            profile.preferred_focus = PreferredFocus(update_data.preferred_focus.value)
        if update_data.coaching_style is not None:
            profile.coaching_style = CoachingStyle(update_data.coaching_style.value)

        await self.session.flush()
        return profile
