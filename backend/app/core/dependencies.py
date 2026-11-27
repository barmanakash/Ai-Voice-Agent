from fastapi import Request

from app.core.config import Config, get_config
from app.database.mongo import MongoManager
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.ollama_service import OllamaService
from app.services.settings_service import SettingsService


def get_ollama(request: Request) -> OllamaService:
    return request.app.state.ollama


def get_settings_service(request: Request) -> SettingsService:
    return request.app.state.settings_service


def get_mongo(request: Request) -> MongoManager:
    return request.app.state.mongo


def get_conversations(request: Request) -> ConversationService:
    return request.app.state.conversations


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_app_config() -> Config:
    return get_config()
