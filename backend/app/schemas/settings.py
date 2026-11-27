from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

WhisperModel = Literal["tiny", "base", "small", "medium", "large-v3"]


class RagSettings(BaseModel):
    chunk_size: int = Field(1000, ge=100, le=4000)
    chunk_overlap: int = Field(200, ge=0, le=1000)
    top_k: int = Field(4, ge=1, le=20)
    min_score: float = Field(0.25, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def overlap_smaller_than_chunk(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class RuntimeSettings(BaseModel):
    """User-editable settings, persisted to backend/data/settings.json."""

    model: str = Field(..., min_length=1, max_length=200)
    context_window: int = Field(4096, ge=512, le=131072)
    history_limit: int = Field(20, ge=1, le=100)
    stt_model: WhisperModel = "base"
    stt_language: str = Field("auto", min_length=2, max_length=10)
    rag: RagSettings = Field(default_factory=RagSettings)

    @field_validator("model", "stt_language")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class ModelInfo(BaseModel):
    name: str
    size: int | None = None
    modified_at: datetime | None = None


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    current: str


class ModelStatus(BaseModel):
    ollama_connected: bool
    model: str
    model_available: bool
    message: str = ""
