from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CoachFeedbackRequest(BaseModel):
    session_id: str
    target_focus: str | None = "form_improvement"


class CoachFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    llm_model: str
    summary: str
    strengths: list[str] = Field(default_factory=list)
    areas_to_improve: list[str] = Field(default_factory=list)
    recovery_advice: str | None = None
    created_at: datetime
