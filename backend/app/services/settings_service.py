import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from app.schemas.settings import RuntimeSettings

logger = logging.getLogger(__name__)


class SettingsService:
    """Holds the editable runtime settings and persists them to a JSON file."""

    def __init__(self, path: Path, defaults: RuntimeSettings):
        self._path = path
        self._defaults = defaults
        self._lock = asyncio.Lock()
        self._current = self._load()

    def _load(self) -> RuntimeSettings:
        if not self._path.exists():
            return self._defaults
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return RuntimeSettings.model_validate(data)
        except (OSError, ValueError, ValidationError):
            logger.warning("Could not read %s; falling back to defaults", self._path)
            return self._defaults

    def get(self) -> RuntimeSettings:
        return self._current

    def _write(self, settings: RuntimeSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file then atomically replace, so a crash never leaves a half-written file
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(settings.model_dump(), f, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    async def update(self, settings: RuntimeSettings) -> RuntimeSettings:
        async with self._lock:
            await asyncio.to_thread(self._write, settings)
            self._current = settings
        return settings
