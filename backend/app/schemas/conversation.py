from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreate(BaseModel):
    title: str | None = Field(None, max_length=80)


class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("title must not be empty")
        return v


class ConversationOut(BaseModel):
    # "model_name" starts with pydantic's protected "model_" prefix
    model_config = ConfigDict(protected_namespaces=())

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    model_name: str | None = None


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    sources: list[dict[str, Any]] = Field(default_factory=list)


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]
