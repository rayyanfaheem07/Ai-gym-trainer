from pydantic import BaseModel, Field


class ExerciseItemResponse(BaseModel):
    name: str = Field(description="Canonical machine identifier (e.g. squat, pushup, bicep_curl)")
    display_name: str = Field(description="Human-readable title")
    category: str = Field(description="Exercise biomechanical category (e.g. compound_lower, push_upper)")
    target_muscles: list[str] = Field(default_factory=list, description="Target muscle groups")
    primary_joints: list[str] = Field(default_factory=list, description="Primary joints tracked")
    description: str = Field(description="Exercise description and movement standards")
    form_rules: list[str] = Field(default_factory=list, description="Form deviation check rules")


class ExerciseListResponse(BaseModel):
    exercises: list[ExerciseItemResponse]
    count: int
