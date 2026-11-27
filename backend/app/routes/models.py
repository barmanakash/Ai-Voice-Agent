from fastapi import APIRouter, Depends

from app.core.dependencies import get_ollama, get_settings_service
from app.schemas.settings import ModelsResponse, ModelStatus
from app.services.ollama_service import OllamaService
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelsResponse)
async def list_models(
    ollama: OllamaService = Depends(get_ollama),
    settings: SettingsService = Depends(get_settings_service),
):
    """Models installed in Ollama. Returns 503 with a helpful message if Ollama is not running."""
    models = await ollama.list_models()
    return ModelsResponse(models=models, current=settings.get().model)


@router.get("/status", response_model=ModelStatus)
async def model_status(
    ollama: OllamaService = Depends(get_ollama),
    settings: SettingsService = Depends(get_settings_service),
):
    """Connectivity + availability of the selected model. Never fails; problems are reported in the body."""
    return await ollama.status(settings.get().model)
