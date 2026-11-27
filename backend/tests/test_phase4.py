"""Phase 4 tests: conversations CRUD, streaming chat, regenerate and persistence.

Uses in-memory fakes, so neither Ollama nor MongoDB is needed.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_chat_service,
    get_conversations,
    get_mongo,
    get_ollama,
    get_settings_service,
)
from app.main import app
from app.schemas.settings import RuntimeSettings
from app.services.chat_service import ChatService, make_title
from app.services.settings_service import SettingsService
from tests.fakes import FakeMongo, FakeOllama, InMemoryConversations


@pytest.fixture
def env(tmp_path):
    """Returns a factory that wires fakes into the app and gives back (client, store, ollama)."""

    def _make(ollama: FakeOllama | None = None):
        ollama = ollama or FakeOllama()
        store = InMemoryConversations()
        svc = SettingsService(tmp_path / "settings.json", RuntimeSettings(model="qwen2.5:3b", history_limit=20))
        chat_service = ChatService(store, ollama, "You are a test assistant.")

        app.dependency_overrides[get_ollama] = lambda: ollama
        app.dependency_overrides[get_mongo] = lambda: FakeMongo()
        app.dependency_overrides[get_settings_service] = lambda: svc
        app.dependency_overrides[get_conversations] = lambda: store
        app.dependency_overrides[get_chat_service] = lambda: chat_service
        return TestClient(app), store, ollama

    yield _make
    app.dependency_overrides.clear()


def stream(client, **body):
    """POST to /chat/stream and return (status_code, [events]) or (status_code, json) on HTTP errors."""
    payload = {"message": "Hi", "use_knowledge_base": False, **body}
    r = client.post("/api/chat/stream", json=payload)
    if r.status_code != 200:
        return r.status_code, r.json()
    return r.status_code, [json.loads(line) for line in r.text.splitlines() if line.strip()]


# ------------------------------------------------------------------ unit
def test_make_title_truncates_and_cleans():
    assert make_title("  hello   world ") == "hello world"
    assert make_title("") == "New chat"
    long = make_title("x" * 200)
    assert long.endswith("…") and len(long) <= 51


# --------------------------------------------------------------- streaming
def test_new_conversation_stream_and_persistence(env):
    client, store, _ = env()
    status, events = stream(client, message="What is Python?")
    assert status == 200

    types = [e["type"] for e in events]
    assert types == ["meta", "token", "token", "token", "done"]
    assert "".join(e["content"] for e in events if e["type"] == "token") == "Hello from Aria"

    meta, done = events[0], events[-1]
    assert meta["title"] == "What is Python?"
    assert done["used_knowledge_base"] is False

    # Persisted: conversation listed, both messages stored in order
    convs = client.get("/api/conversations").json()
    assert [c["id"] for c in convs] == [meta["conversation_id"]]
    detail = client.get(f"/api/conversations/{meta['conversation_id']}").json()
    assert [(m["role"], m["content"]) for m in detail["messages"]] == [
        ("user", "What is Python?"),
        ("assistant", "Hello from Aria"),
    ]
    assert detail["messages"][1]["id"] == done["message_id"]


def test_follow_up_sends_history_to_model(env):
    client, _, ollama = env()
    _, first = stream(client, message="My name is Sam")
    cid = first[0]["conversation_id"]

    stream(client, message="What is my name?", conversation_id=cid)
    roles = [m["role"] for m in ollama.last_messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert ollama.last_messages[1]["content"] == "My name is Sam"
    assert ollama.last_messages[-1]["content"] == "What is my name?"


def test_history_limit_is_applied(env, tmp_path):
    client, _, ollama = env()
    _, first = stream(client, message="m0")
    cid = first[0]["conversation_id"]
    for i in range(1, 6):
        stream(client, message=f"m{i}", conversation_id=cid)

    client.put("/api/settings", json={**client.get("/api/settings").json(), "history_limit": 2})
    stream(client, message="latest", conversation_id=cid)
    # system + 2 history messages + new user message
    assert len(ollama.last_messages) == 4


def test_regenerate_replaces_last_answer(env):
    ollama = FakeOllama(chunks=("First answer",))
    client, store, _ = env(ollama)
    _, events = stream(client, message="Tell me a joke")
    cid, user_id = events[0]["conversation_id"], events[0]["user_message_id"]
    old_answer_id = events[-1]["message_id"]

    ollama.chunks = ["Second answer"]
    status, events = stream(client, message="Tell me a joke", conversation_id=cid, regenerate=True)
    assert status == 200
    assert events[0]["user_message_id"] == user_id  # same user message reused

    detail = client.get(f"/api/conversations/{cid}").json()
    assert [(m["role"], m["content"]) for m in detail["messages"]] == [
        ("user", "Tell me a joke"),
        ("assistant", "Second answer"),
    ]
    assert detail["messages"][1]["id"] != old_answer_id
    # the old answer must not leak into the prompt used for regeneration
    assert all("First answer" not in m["content"] for m in ollama.last_messages)


def test_regenerate_without_conversation_is_400(env):
    client, _, _ = env()
    status, body = stream(client, regenerate=True)
    assert status == 400


def test_regenerate_empty_conversation_is_400(env):
    client, _, _ = env()
    cid = client.post("/api/conversations", json={}).json()["id"]
    status, body = stream(client, conversation_id=cid, regenerate=True)
    assert status == 400


def test_unknown_or_invalid_conversation_is_404(env):
    client, _, _ = env()
    assert stream(client, conversation_id="f" * 24)[0] == 404
    assert stream(client, conversation_id="not-an-id")[0] == 404
    assert client.get("/api/conversations/not-an-id").status_code == 404


def test_stream_error_midway_keeps_partial_answer(env):
    client, _, _ = env(FakeOllama(chunks=("Partial", " text", " more"), fail_after=2))
    status, events = stream(client, message="Hello")
    assert [e["type"] for e in events] == ["meta", "token", "token", "error"]
    assert "went away" in events[-1]["detail"]

    cid = events[0]["conversation_id"]
    msgs = client.get(f"/api/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"] == "Partial text"


def test_error_before_any_token_saves_no_assistant_message(env):
    client, _, _ = env(FakeOllama(chunks=("x",), fail_after=0))
    _, events = stream(client, message="Hello")
    assert events[-1]["type"] == "error"
    cid = events[0]["conversation_id"]
    msgs = client.get(f"/api/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user"]


def test_missing_model_fails_before_creating_anything(env):
    client, store, _ = env(FakeOllama(installed=["other:1b"]))
    status, body = stream(client, message="Hi")
    assert status == 424
    assert "not installed" in body["detail"]
    assert client.get("/api/conversations").json() == []


def test_ollama_offline_is_503_and_creates_nothing(env):
    client, _, _ = env(FakeOllama(online=False))
    status, _ = stream(client, message="Hi")
    assert status == 503
    assert client.get("/api/conversations").json() == []


def test_stream_validation(env):
    client, _, _ = env()
    assert client.post("/api/chat/stream", json={"message": ""}).status_code == 422
    assert client.post("/api/chat/stream", json={"message": "   "}).status_code == 422
    assert client.post("/api/chat/stream", json={}).status_code == 422


# ------------------------------------------------------------ conversations
def test_create_rename_delete_flow(env):
    client, _, _ = env()
    created = client.post("/api/conversations", json={"title": "  My   chat "})
    assert created.status_code == 201
    conv = created.json()
    assert conv["title"] == "My chat"
    assert conv["model_name"] == "qwen2.5:3b"

    renamed = client.patch(f"/api/conversations/{conv['id']}", json={"title": "Renamed"})
    assert renamed.status_code == 200 and renamed.json()["title"] == "Renamed"
    assert client.patch(f"/api/conversations/{conv['id']}", json={"title": "  "}).status_code == 422

    assert client.delete(f"/api/conversations/{conv['id']}").status_code == 204
    assert client.get(f"/api/conversations/{conv['id']}").status_code == 404
    assert client.delete(f"/api/conversations/{conv['id']}").status_code == 404


def test_default_title_for_empty_create(env):
    client, _, _ = env()
    assert client.post("/api/conversations", json={}).json()["title"] == "New chat"


def test_delete_removes_messages(env):
    client, store, _ = env()
    _, events = stream(client, message="Hi")
    cid = events[0]["conversation_id"]
    assert len(store.messages) == 2
    client.delete(f"/api/conversations/{cid}")
    assert store.messages == {}


def test_clear_history_keeps_conversation(env):
    client, _, _ = env()
    _, events = stream(client, message="Hi")
    cid = events[0]["conversation_id"]

    assert client.delete(f"/api/conversations/{cid}/messages").status_code == 204
    detail = client.get(f"/api/conversations/{cid}").json()
    assert detail["messages"] == []
    assert detail["title"] == "Hi"


def test_conversations_sorted_by_recent_activity(env):
    client, _, _ = env()
    _, a = stream(client, message="first")
    _, b = stream(client, message="second")
    stream(client, message="again", conversation_id=a[0]["conversation_id"])  # bumps "first"

    ids = [c["id"] for c in client.get("/api/conversations").json()]
    assert ids == [a[0]["conversation_id"], b[0]["conversation_id"]]
