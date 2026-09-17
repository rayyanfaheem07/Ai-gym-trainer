from backend.app.api.deps import get_current_user
from backend.app.models.user import User
from backend.app.schemas.analysis import AnalysisRequest, AnalysisResponse
from backend.app.services.analysis_service import AnalysisService
from fastapi import APIRouter, Depends, status

router = APIRouter()


@router.post(
    "",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Process AI pose and exercise form analysis",
    description="Accepts 2D/3D pose landmarks and optional exercise hints to return exercise recognition, repetition progress, and form deviations.",
)
async def analyze_pose_frame(
    request: AnalysisRequest,
    current_user: User = Depends(get_current_user),
) -> AnalysisResponse:
    """Analyze a single landmark frame or temporal sequence of frames for authenticated user."""
    return AnalysisService.process_analysis(request)

