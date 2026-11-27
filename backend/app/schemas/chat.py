from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_CHARS = 8000


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    """Stateless chat request: the caller supplies the history. Nothing is saved."""

    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=100)
    model: str | None = Field(None, max_length=200)

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        return v


class ChatReply(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatResponse(BaseModel):
    message: ChatReply
    model: str


class ChatStreamRequest(BaseModel):
    """Persistent, streaming chat turn. History comes from MongoDB, not from the client."""

    conversation_id: str | None = Field(None, max_length=64)
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    use_knowledge_base: bool = True  # honoured from Phase 6 onwards
    regenerate: bool = False
    model: str | None = Field(None, max_length=200)

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        return v
