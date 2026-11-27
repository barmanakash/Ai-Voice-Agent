from fastapi import APIRouter, Depends

from app.core.dependencies import get_ollama, get_settings_service
from app.core.errors import OllamaUnavailableError
from app.schemas.settings import RuntimeSettings
from app.services.ollama_service import OllamaService
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=RuntimeSettings)
async def get_settings(settings: SettingsService = Depends(get_settings_service)):
    return settings.get()


@router.put("", response_model=RuntimeSettings)
async def update_settings(
    body: RuntimeSettings,
    settings: SettingsService = Depends(get_settings_service),
    ollama: OllamaService = Depends(get_ollama),
):
    """Save settings. A changed model must be installed in Ollama (checked when Ollama is reachable)."""
    if body.model != settings.get().model:
        try:
            await ollama.ensure_model(body.model)  # raises 424 if the model is missing
        except OllamaUnavailableError:
            pass  # Ollama is offline: we can't verify, so accept and let chat report the problem
    return await settings.update(body)
