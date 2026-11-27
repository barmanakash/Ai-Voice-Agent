import axios from "axios";

/**
 * Central API client. All requests go through the Vite proxy (/api -> FastAPI).
 *
 * Streaming protocol for POST /api/chat/stream (newline-delimited JSON, one
 * object per line) that the backend must follow:
 *   {"type":"meta",    "conversation_id":"...", "user_message_id":"...", "title":"..."}
 *   {"type":"sources", "sources":[{document_id, document_name, chunk_id, page, score, snippet}]}
 *   {"type":"token",   "content":"partial text"}
 *   {"type":"done",    "message_id":"...", "used_knowledge_base":true|false}
 *   {"type":"error",   "detail":"human readable message"}
 */
export const http = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

/** Convert any axios/fetch error into a short human readable string. */
export function getErrorMessage(err, fallback = "Something went wrong") {
  if (err?.name === "AbortError") return "Request cancelled";
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  if (err?.code === "ECONNABORTED") return "The request timed out";
  if (err?.message === "Network Error")
    return "Cannot reach the backend. Is the FastAPI server running on port 8000?";
  return err?.message || fallback;
}

/* ----------------------------- Conversations ----------------------------- */
export const conversationsApi = {
  list: () => http.get("/conversations").then((r) => r.data),
  create: (payload = {}) => http.post("/conversations", payload).then((r) => r.data),
  get: (id) => http.get(`/conversations/${id}`).then((r) => r.data),
  rename: (id, title) => http.patch(`/conversations/${id}`, { title }).then((r) => r.data),
  remove: (id) => http.delete(`/conversations/${id}`).then((r) => r.data),
  clear: (id) => http.delete(`/conversations/${id}/messages`).then((r) => r.data),
};

/* -------------------------------- Documents ------------------------------- */
export const documentsApi = {
  list: () => http.get("/documents").then((r) => r.data),
  get: (id) => http.get(`/documents/${id}`).then((r) => r.data),
  status: (id) => http.get(`/documents/${id}/status`).then((r) => r.data),
  remove: (id) => http.delete(`/documents/${id}`).then((r) => r.data),
  upload: (file, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    return http
      .post("/documents/upload", form, {
        timeout: 0, // large files: let the backend take its time
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
        },
      })
      .then((r) => r.data);
  },
};

/* --------------------------------- Models --------------------------------- */
export const modelsApi = {
  list: () => http.get("/models").then((r) => r.data),
  status: () => http.get("/models/status", { timeout: 8000 }).then((r) => r.data),
};

/* -------------------------------- Settings -------------------------------- */
export const settingsApi = {
  get: () => http.get("/settings").then((r) => r.data),
  update: (payload) => http.put("/settings", payload).then((r) => r.data),
};

/* ---------------------------------- Voice --------------------------------- */
export const voiceApi = {
  voices: () => http.get("/voice/voices").then((r) => r.data),
  transcribe: (blob) => {
    const form = new FormData();
    const ext = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "m4a" : "webm";
    form.append("audio", blob, `recording.${ext}`);
    return http.post("/voice/transcribe", form, { timeout: 120000 }).then((r) => r.data);
  },
  /** Returns a Blob (audio/wav) */
  speak: (text, voice) =>
    http
      .post("/voice/speak", { text, voice }, { responseType: "blob", timeout: 120000 })
      .then((r) => r.data),
};

/* ------------------------------ Streaming chat ----------------------------- */
/**
 * Stream a chat response. Uses fetch (not axios) because we need a readable
 * stream and AbortController support to implement "Stop generation".
 *
 * @param {object} body  { conversation_id, message, use_knowledge_base, regenerate }
 * @param {object} handlers { onMeta, onSources, onToken, onDone, onError }
 * @param {AbortSignal} signal
 */
export async function streamChat(body, handlers, signal) {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (line) => {
    if (!line.trim()) return;
    let evt;
    try {
      evt = JSON.parse(line);
    } catch {
      return; // ignore malformed line
    }
    switch (evt.type) {
      case "meta":
        handlers.onMeta?.(evt);
        break;
      case "sources":
        handlers.onSources?.(evt.sources || []);
        break;
      case "token":
        handlers.onToken?.(evt.content || "");
        break;
      case "done":
        handlers.onDone?.(evt);
        break;
      case "error":
        handlers.onError?.(evt.detail || "The model returned an error");
        break;
      default:
        break;
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    lines.forEach(dispatch);
  }
  if (buffer) dispatch(buffer);
}
