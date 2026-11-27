"""Phase 3 tests: health, models, settings and stateless chat.

A fake Ollama service replaces the real one, so these tests need no Ollama install.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_mongo, get_ollama, get_settings_service
from app.core.errors import ModelNotAvailableError, OllamaUnavailableError
from app.main import app
from app.schemas.settings import RuntimeSettings
from app.services.ollama_service import build_chat_messages, model_is_installed
from app.services.settings_service import SettingsService
from tests.fakes import FakeMongo


class FakeOllama:
    def __init__(self, installed=("qwen2.5:3b",), online=True):
        self.installed = list(installed)
        self.online = online
        self.last_messages = None

    async def list_models(self):
        if not self.online:
            raise OllamaUnavailableError("Cannot connect to Ollama")
        return [{"name": n, "size": 1000, "modified_at": None} for n in self.installed]

    async def status(self, model):
        try:
            names = [m["name"] for m in await self.list_models()]
        except OllamaUnavailableError as exc:
            return {"ollama_connected": False, "model": model, "model_available": False, "message": exc.detail}
        ok = model_is_installed(model, names)
        return {"ollama_connected": True, "model": model, "model_available": ok,
                "message": "" if ok else f"missing {model}"}

    async def ensure_model(self, model):
        names = [m["name"] for m in await self.list_models()]
        if not model_is_installed(model, names):
            raise ModelNotAvailableError(f"Model {model} is not installed")

    async def chat(self, messages, model, num_ctx):
        await self.ensure_model(model)
        self.last_messages = messages
        return "Hello from the fake model"


@pytest.fixture
def make_client(tmp_path):
    def _make(fake: FakeOllama):
        defaults = RuntimeSettings(model="qwen2.5:3b")
        svc = SettingsService(tmp_path / "settings.json", defaults)
        app.dependency_overrides[get_ollama] = lambda: fake
        app.dependency_overrides[get_mongo] = lambda: FakeMongo()
        app.dependency_overrides[get_settings_service] = lambda: svc
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


# ----------------------------------------------------------------- unit tests
def test_model_is_installed_handles_latest_tag():
    assert model_is_installed("llama3", ["llama3:latest"])
    assert model_is_installed("qwen2.5:3b", ["qwen2.5:3b"])
    assert not model_is_installed("qwen2.5:3b", ["qwen2.5:7b"])


def test_build_messages_limits_history():
    history = [{"role": "user", "content": str(i)} for i in range(10)]
    msgs = build_chat_messages("sys", history, "new", history_limit=3)
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert [m["content"] for m in msgs[1:-1]] == ["7", "8", "9"]
    assert msgs[-1] == {"role": "user", "content": "new"}


# ------------------------------------------------------------------ API tests
def test_health_ok_even_when_ollama_offline(make_client):
    client = make_client(FakeOllama(online=False))
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["ollama_connected"] is False


def test_model_status_connected_and_available(make_client):
    r = make_client(FakeOllama()).get("/api/models/status")
    assert r.status_code == 200
    assert r.json()["ollama_connected"] and r.json()["model_available"]


def test_model_status_missing_model(make_client):
    r = make_client(FakeOllama(installed=["other:1b"])).get("/api/models/status")
    body = r.json()
    assert body["ollama_connected"] is True
    assert body["model_available"] is False
    assert "missing" in body["message"]


def test_models_list_and_offline_error(make_client):
    r = make_client(FakeOllama(installed=["a:1b", "b:2b"])).get("/api/models")
    assert [m["name"] for m in r.json()["models"]] == ["a:1b", "b:2b"]
    assert r.json()["current"] == "qwen2.5:3b"

    r = make_client(FakeOllama(online=False)).get("/api/models")
    assert r.status_code == 503
    assert "Cannot connect" in r.json()["detail"]


def test_chat_happy_path_uses_history(make_client):
    fake = FakeOllama()
    client = make_client(fake)
    r = client.post("/api/chat", json={
        "message": "  hi there ",
        "history": [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "reply"}],
    })
    assert r.status_code == 200
    assert r.json()["message"]["content"] == "Hello from the fake model"
    roles = [m["role"] for m in fake.last_messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert fake.last_messages[-1]["content"] == "hi there"


def test_chat_missing_model_returns_424(make_client):
    r = make_client(FakeOllama(installed=["other:1b"])).post("/api/chat", json={"message": "hi"})
    assert r.status_code == 424
    assert "not installed" in r.json()["detail"]


def test_chat_ollama_offline_returns_503(make_client):
    r = make_client(FakeOllama(online=False)).post("/api/chat", json={"message": "hi"})
    assert r.status_code == 503


def test_chat_validation(make_client):
    client = make_client(FakeOllama())
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={"message": "   "}).status_code == 422
    bad_role = {"message": "hi", "history": [{"role": "system", "content": "x"}]}
    assert client.post("/api/chat", json=bad_role).status_code == 422


def test_settings_roundtrip_and_validation(make_client):
    client = make_client(FakeOllama())
    current = client.get("/api/settings").json()
    assert current["model"] == "qwen2.5:3b"

    current["history_limit"] = 8
    current["rag"]["chunk_size"] = 800
    r = client.put("/api/settings", json=current)
    assert r.status_code == 200
    assert client.get("/api/settings").json()["history_limit"] == 8

    current["rag"]["chunk_overlap"] = 900  # >= chunk_size
    r = client.put("/api/settings", json=current)
    assert r.status_code == 422
    assert "chunk_overlap" in r.json()["detail"]


def test_settings_rejects_uninstalled_model(make_client):
    client = make_client(FakeOllama())
    current = client.get("/api/settings").json()
    current["model"] = "does-not-exist:1b"
    r = client.put("/api/settings", json=current)
    assert r.status_code == 424
