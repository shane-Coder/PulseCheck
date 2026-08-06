from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    period_seconds: int = Field(gt=0, default=86400)
    grace_seconds: int = Field(ge=0, default=3600)


class MonitorOut(BaseModel):
    id: int
    name: str
    ping_token: str
    period_seconds: int
    grace_seconds: int
    status: str
    last_ping_at: datetime | None

    class Config:
        from_attributes = True
