from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.config import Config
from app.core.dependencies import get_app_config, get_mongo, get_ollama, get_settings_service
from app.database.mongo import MongoManager
from app.services.ollama_service import OllamaService
from app.services.settings_service import SettingsService

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(
    config: Config = Depends(get_app_config),
    ollama: OllamaService = Depends(get_ollama),
    mongo: MongoManager = Depends(get_mongo),
    settings: SettingsService = Depends(get_settings_service),
):
    """Liveness check. Always returns 200 as long as the API itself is up."""
    status = await ollama.status(settings.get().model)
    return {
        "status": "ok",
        "app": config.app_name,
        "version": config.app_version,
        "environment": config.environment,
        "time": datetime.now(timezone.utc).isoformat(),
        "ollama_connected": status["ollama_connected"],
        "model_available": status["model_available"],
        "mongodb_connected": await mongo.ping(),
    }
