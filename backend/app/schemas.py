from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    reply: str


class ResumeFormRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1)
    education_level: str = Field(..., min_length=1)
    skills: str = Field(..., min_length=1)
    work_experience: str = Field(..., min_length=1)
    career_goal: str = Field(default="")


class ResumeFormResponse(BaseModel):
    reply: str
    preview: str

