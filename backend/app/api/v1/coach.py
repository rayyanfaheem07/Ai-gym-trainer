from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.coach import CoachFeedbackRequest, CoachFeedbackResponse
from backend.app.services.coach_service import CoachService
from backend.app.services.workout_service import WorkoutService
from fastapi import APIRouter, Depends, Query
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
) -> CoachFeedbackResponse:
    """Generate LLM-driven post-workout feedback and recovery advice for owned workout session."""
    feedback = await CoachService.generate_feedback(
        db,
        session_id=data.session_id,
        target_focus=data.target_focus or "form_improvement",
        user_id=current_user.id,
    )
    return CoachService.to_response_dto(feedback)


@router.post(
    "/session/{session_id}",
    response_model=CoachFeedbackResponse,
    summary="Evaluate workout session by ID",
    description="RESTful endpoint to trigger AI Coach analysis on a specific authenticated workout session.",
)
async def evaluate_workout_session(
    session_id: str,
    target_focus: str = Query(default="form_improvement", description="Primary focus area for the coaching assessment"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoachFeedbackResponse:
    """Evaluate a specific workout session using AI Coach with verified backend telemetry context."""
    feedback = await CoachService.generate_feedback(
        db,
        session_id=session_id,
        target_focus=target_focus,
        user_id=current_user.id,
    )
    return CoachService.to_response_dto(feedback)


@router.get(
    "/session/{session_id}",
    response_model=CoachFeedbackResponse,
    summary="Get existing coaching feedback for a workout session",
    description="Retrieves previously generated AI coaching feedback for an owned workout session.",
)
async def get_workout_coaching(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoachFeedbackResponse:
    """Retrieve existing post-workout AI coaching feedback."""
    workout = await WorkoutService.get_workout(db, workout_id=session_id, user_id=current_user.id)
    if not workout.feedback:
        # If no feedback generated yet, generate it on demand
        feedback = await CoachService.generate_feedback(
            db,
            session_id=session_id,
            user_id=current_user.id,
        )
    else:
        feedback = workout.feedback

    return CoachService.to_response_dto(feedback)
