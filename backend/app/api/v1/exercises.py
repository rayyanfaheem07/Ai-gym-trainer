from backend.app.schemas.exercise import ExerciseListResponse
from backend.app.services.exercise_service import ExerciseService
from fastapi import APIRouter

router = APIRouter()


@router.get(
    "",
    response_model=ExerciseListResponse,
    summary="List all supported exercises",
    description="Returns the catalog of all exercises supported by the AI Gym Trainer pose and form analysis engine.",
)
async def list_exercises() -> ExerciseListResponse:
    """Retrieve supported exercise definitions and biomechanical standards."""
    return ExerciseService.get_supported_exercises()
