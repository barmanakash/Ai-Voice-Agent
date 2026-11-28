import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_config
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.database.mongo import MongoManager
from app.routes import chat, conversations, documents, health, models, settings
from app.schemas.settings import RuntimeSettings
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.document_pipeline import DocumentPipeline
from app.services.document_service import DocumentService
from app.services.file_storage import FileStorage
from app.services.ollama_service import OllamaService
from app.services.settings_service import SettingsService

config = get_config()
setup_logging(config.log_level)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.data_dir.mkdir(parents=True, exist_ok=True)

    defaults = RuntimeSettings(model=config.ollama_model, context_window=config.ollama_context_window,
                               history_limit=config.history_limit)
    app.state.settings_service = SettingsService(config.runtime_settings_path, defaults)
    app.state.ollama = OllamaService(config.ollama_base_url, config.ollama_timeout)

    # MongoDB: the app still starts if it is down; requests then return a clear 503 message.
    app.state.mongo = MongoManager(config.mongodb_uri, config.mongodb_db, config.mongodb_timeout_ms)
    if await app.state.mongo.ping():
        await app.state.mongo.ensure_indexes()
        logger.info("MongoDB connected (database: %s)", config.mongodb_db)
    else:
        logger.warning("MongoDB is not reachable. Check MONGODB_URI (and the Atlas Network Access list); conversations will not work until it connects.")

    app.state.conversations = ConversationService(app.state.mongo.db)
    app.state.chat_service = ChatService(app.state.conversations, app.state.ollama, config.system_prompt)

    app.state.documents = DocumentService(app.state.mongo.db)
    app.state.file_storage = FileStorage(config.uploads_dir)
    app.state.pipeline = DocumentPipeline(
        app.state.documents,
        app.state.file_storage,
        app.state.settings_service,
        indexer=None,  # Phase 6 plugs in embeddings + ChromaDB here
        max_concurrent=config.max_concurrent_processing,
    )
    try:
        interrupted = await app.state.documents.fail_unfinished(
            "Processing was interrupted because the server restarted. Delete this document and upload it again."
        )
        if interrupted:
            logger.warning("Marked %d interrupted document(s) as failed", interrupted)
    except Exception as exc:
        logger.warning("Could not check for interrupted documents: %s", type(exc).__name__)

    current = app.state.settings_service.get()
    status = await app.state.ollama.status(current.model)
    if not status["ollama_connected"]:
        logger.warning("Ollama is not reachable at %s. %s", config.ollama_base_url, status["message"])
    elif not status["model_available"]:
        logger.warning(status["message"])
    else:
        logger.info("Ollama ready. Using model %s", current.model)

    yield

    await app.state.ollama.close()
    await app.state.mongo.close()


app = FastAPI(title=config.app_name, version=config.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

register_exception_handlers(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, ms)
    return response


for router in (health.router, models.router, settings.router, conversations.router, chat.router, documents.router):
    app.include_router(router, prefix="/api")
