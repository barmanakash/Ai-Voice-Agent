# Aria — Local AI Voice Chatbot with Knowledge Base

A fully local chatbot: Ollama for the LLM, RAG over your own documents, and voice in/out
(faster-whisper for STT, Piper for TTS). No cloud AI services are required.

```
AI-Voice-Agent/
├── frontend/   React + Vite + Tailwind UI
└── backend/    FastAPI + Ollama + ChromaDB + MongoDB   (next phase)
```

## Prerequisites

- Node.js 18+ (frontend)
- Python 3.10+ (backend, later phases)
- [Ollama](https://ollama.com/download) with at least one model, e.g. `ollama pull qwen2.5:3b`
- MongoDB Community Server running on `localhost:27017` (backend, later phases)

## Run the frontend (Windows PowerShell)

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open http://localhost:5173.

## Run the backend (Windows PowerShell)

Make sure MongoDB is running and Ollama is running with a model installed (`ollama pull qwen2.5:3b`), then:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks the activate script, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

API docs: http://127.0.0.1:8000/docs · Health: http://127.0.0.1:8000/api/health

### Run the backend tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```

The tests use in-memory fakes, so they pass even if Ollama and MongoDB are not installed.

The dev server proxies `/api/*` to `VITE_BACKEND_URL` (default `http://localhost:8000`).

## Progress checklist

- [x] Phase 1 — Project initialization and configuration (frontend)
- [x] Phase 2 — React frontend and chatbot UI (written, needs first run/test)
- [x] Phase 3 — FastAPI backend and Ollama integration (health, models, settings, stateless `/api/chat`; needs first run/test)
- [x] Phase 4 — Conversation history and streaming (MongoDB, `/api/chat/stream`, regenerate, rename, delete, clear; needs first run/test)
- [x] Phase 5 — Document upload and processing (validation, PDF/DOCX/TXT/MD extraction, cleaning, chunking, status tracking, delete; documents are chunked but not yet searchable until Phase 6; needs first run/test)
- [ ] Phase 6 — ChromaDB and RAG
- [ ] Phase 7 — Speech-to-text
- [ ] Phase 8 — Text-to-speech
- [ ] Phase 9 — Voice conversation mode (UI done, needs backend)
- [ ] Phase 10 — Testing, optimization, documentation

## API contract the frontend expects

Everything under `/api`. IDs are strings. Timestamps are ISO-8601.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | liveness |
| GET | `/models` | `{ models: [{name, size, modified_at}], current }` |
| GET | `/models/status` | `{ ollama_connected, model, model_available, message }` |
| GET / PUT | `/settings` | `{ model, context_window, history_limit, stt_model, stt_language, rag: {chunk_size, chunk_overlap, top_k, min_score} }` |
| GET | `/conversations` | `[{id, title, created_at, updated_at, model_name}]` newest first |
| POST | `/conversations` | body `{title?}` |
| GET | `/conversations/{id}` | conversation + `messages: [{id, role, content, created_at, sources}]` |
| PATCH | `/conversations/{id}` | body `{title}` → updated conversation |
| DELETE | `/conversations/{id}` | |
| DELETE | `/conversations/{id}/messages` | clear history |
| POST | `/chat` | non-streaming variant |
| POST | `/chat/stream` | body `{conversation_id\|null, message, use_knowledge_base, regenerate}`; NDJSON stream (below) |
| POST | `/documents/upload` | multipart field `file`; 409 on duplicate |
| GET | `/documents` | `[{id, filename, file_type, file_size, processing_status, chunk_count, progress, error, uploaded_at}]` |
| GET | `/documents/{id}` , `/documents/{id}/status` | |
| DELETE | `/documents/{id}` | also deletes file + vectors |
| GET | `/voice/voices` | `{ voices: [{id, name, language}], default }` |
| POST | `/voice/transcribe` | multipart field `audio` → `{ text, language }` |
| POST | `/voice/speak` | body `{text, voice?}` → `audio/wav` |
| POST | `/voice/chat` | single-call voice round trip |

`processing_status`: `pending` · `processing` · `completed` · `failed`.

### Streaming format for `POST /chat/stream`

One JSON object per line:

```
{"type":"meta","conversation_id":"…","user_message_id":"…","title":"…"}
{"type":"sources","sources":[{"document_id","document_name","chunk_id","page","score","snippet"}]}
{"type":"token","content":"partial text"}
{"type":"done","message_id":"…","used_knowledge_base":true}
{"type":"error","detail":"human readable message"}
```

When `regenerate` is true, the backend replaces the last assistant message instead of adding a new user message.
