from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.coach import CoachFeedbackRequest, CoachFeedbackResponse
from backend.app.services.coach_service import CoachService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "/evaluate",
    response_model=CoachFeedbackResponse,
    summary="Evaluate workout and provide coaching insights",
    description="Generates AI coaching insights, strengths, and form recommendations for an authenticated user's workout.",
)
async def evaluate_workout(
    data: CoachFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate LLM-driven post-workout feedback and recovery advice for owned workout session."""
    feedback = await CoachService.generate_feedback(
        db,
        session_id=data.session_id,
        target_focus=data.target_focus or "form_improvement",
        user_id=current_user.id,
    )
    return feedback

