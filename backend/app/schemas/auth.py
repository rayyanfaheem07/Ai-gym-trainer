import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegister(BaseModel):
    email: str = Field(description="User email address")
    password: str = Field(min_length=8, description="User password (minimum 8 characters)")
    full_name: str | None = Field(default=None, max_length=255, description="Optional full name")

    @field_validator("email", mode="before")
    @classmethod
    def validate_and_normalize_email(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Email cannot be empty.")
        clean = v.strip().lower()
        email_regex = r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, clean):
            raise ValueError("Invalid email address format.")
        return clean

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if v.isdigit():
            raise ValueError("Password cannot consist solely of digits.")
        if v.isalpha():
            raise ValueError("Password must contain at least one digit or special character.")
        return v


class UserLogin(BaseModel):
    email: str = Field(description="Registered email address")
    password: str = Field(description="Account password")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None



class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse | None = None
