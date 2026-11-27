"""Ollama integration. Only this module talks to the Ollama SDK."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from ollama import AsyncClient, ResponseError

from app.core.errors import AppError, ModelNotAvailableError, OllamaUnavailableError

logger = logging.getLogger(__name__)

# Short timeout for cheap "is it alive / what's installed" calls
QUICK_TIMEOUT = 5.0


def model_is_installed(requested: str, installed: list[str]) -> bool:
    """Ollama treats "name" and "name:latest" as the same model."""
    if requested in installed:
        return True
    if ":" not in requested:
        return f"{requested}:latest" in installed
    return False


def build_chat_messages(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
    history_limit: int,
) -> list[dict[str, str]]:
    """System prompt + the most recent `history_limit` messages + the new user message."""
    recent = history[-history_limit:] if history_limit > 0 else []
    return [
        {"role": "system", "content": system_prompt},
        *({"role": m["role"], "content": m["content"]} for m in recent),
        {"role": "user", "content": user_message},
    ]


class OllamaService:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url
        self._client = AsyncClient(host=base_url, timeout=timeout)

    async def close(self) -> None:
        try:
            await self._client._client.aclose()  # underlying httpx.AsyncClient
        except Exception:  # pragma: no cover - best effort on shutdown
            pass

    # ------------------------------------------------------------------ errors
    def _translate(self, exc: Exception, model: str | None = None) -> AppError:
        if isinstance(exc, AppError):
            return exc
        if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
            return OllamaUnavailableError(
                "Ollama did not respond in time. The model may still be loading; try again in a moment."
            )
        if isinstance(exc, (ConnectionError, httpx.TransportError)):
            return OllamaUnavailableError(
                f"Cannot connect to Ollama at {self.base_url}. Start it with: ollama serve"
            )
        if isinstance(exc, ResponseError):
            if exc.status_code == 404 and model:
                return ModelNotAvailableError(
                    f'Model "{model}" is not installed in Ollama. Install it with: ollama pull {model}'
                )
            logger.error("Ollama returned an error (%s): %s", exc.status_code, exc.error)
            return AppError(f"Ollama error: {exc.error}", status_code=502)
        logger.exception("Unexpected error while talking to Ollama")
        return AppError("Unexpected error while talking to Ollama", status_code=502)

    # ------------------------------------------------------------------ models
    async def list_models(self) -> list[dict[str, Any]]:
        try:
            resp = await asyncio.wait_for(self._client.list(), timeout=QUICK_TIMEOUT)
        except Exception as exc:
            raise self._translate(exc) from exc

        models = []
        for m in resp.models:
            name = getattr(m, "model", None) or getattr(m, "name", None)
            if name:
                models.append(
                    {"name": name, "size": getattr(m, "size", None), "modified_at": getattr(m, "modified_at", None)}
                )
        return sorted(models, key=lambda m: m["name"])

    async def status(self, model: str) -> dict[str, Any]:
        """Never raises: reports connectivity and whether `model` is installed."""
        try:
            installed = [m["name"] for m in await self.list_models()]
        except AppError as exc:
            return {"ollama_connected": False, "model": model, "model_available": False, "message": exc.detail}

        available = model_is_installed(model, installed)
        message = "" if available else f'Model "{model}" is not installed. Run: ollama pull {model}'
        return {"ollama_connected": True, "model": model, "model_available": available, "message": message}

    async def ensure_model(self, model: str) -> None:
        """Raise a helpful error if Ollama is down or the model is missing."""
        installed = [m["name"] for m in await self.list_models()]
        if not model_is_installed(model, installed):
            raise ModelNotAvailableError(
                f'Model "{model}" is not installed in Ollama. Install it with: ollama pull {model}'
            )

    # -------------------------------------------------------------------- chat
    async def chat(self, messages: list[dict[str, str]], model: str, num_ctx: int) -> str:
        await self.ensure_model(model)
        try:
            resp = await self._client.chat(model=model, messages=messages, options={"num_ctx": num_ctx})
        except Exception as exc:
            raise self._translate(exc, model) from exc
        return resp.message.content or ""

    async def chat_stream(self, messages: list[dict[str, str]], model: str, num_ctx: int) -> AsyncIterator[str]:
        """Yield response text chunks as Ollama generates them (used for streaming in Phase 4)."""
        await self.ensure_model(model)
        try:
            stream = await self._client.chat(
                model=model, messages=messages, options={"num_ctx": num_ctx}, stream=True
            )
            async for part in stream:
                chunk = part.message.content
                if chunk:
                    yield chunk
        except Exception as exc:
            raise self._translate(exc, model) from exc
