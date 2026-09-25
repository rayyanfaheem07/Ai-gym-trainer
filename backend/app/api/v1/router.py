from backend.app.api.v1.analysis import router as analysis_router
from backend.app.api.v1.analytics import router as analytics_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.coach import router as coach_router
from backend.app.api.v1.exercises import router as exercises_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.profile import router as profile_router
from backend.app.api.v1.websocket import router as ws_router
from backend.app.api.v1.workouts import router as workouts_router
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(profile_router, prefix="/profile", tags=["Profile"])
api_router.include_router(workouts_router, prefix="/workouts", tags=["Workouts"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(exercises_router, prefix="/exercises", tags=["Exercises"])
api_router.include_router(analysis_router, prefix="/analysis", tags=["AI Analysis"])
api_router.include_router(coach_router, prefix="/coach", tags=["AI Coach"])
api_router.include_router(ws_router, prefix="/ws", tags=["Real-Time Streaming"])


