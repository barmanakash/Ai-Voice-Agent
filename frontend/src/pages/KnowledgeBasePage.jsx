import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  Menu,
  RefreshCw,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { documentsApi, getErrorMessage } from "../services/api.js";
import { useApp } from "../context/AppContext.jsx";
import {
  ACCEPTED_DOC_TYPES,
  MAX_UPLOAD_MB,
  formatBytes,
  formatDateTime,
  validateDocument,
} from "../utils/format.js";

const ACTIVE = ["pending", "processing"];

function StatusBadge({ doc }) {
  const s = doc.processing_status;
  if (s === "completed")
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-400">
        <CheckCircle2 size={12} /> Ready
      </span>
    );
  if (s === "failed")
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-xs text-red-400">
        <AlertCircle size={12} /> Failed
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">
      {s === "pending" ? <Clock size={12} /> : <Loader2 size={12} className="animate-spin" />}
      {s === "pending" ? "Queued" : "Processing"}
    </span>
  );
}

export default function KnowledgeBasePage() {
  const { setSidebarOpen } = useApp();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [uploads, setUploads] = useState([]); // in-flight uploads {key, name, progress, error}
  const [dragging, setDragging] = useState(false);
  const [confirmId, setConfirmId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [actionError, setActionError] = useState("");
  const fileRef = useRef(null);

  const load = useCallback(async (silent = false) => {
    try {
      const data = await documentsApi.list();
      setDocs(data);
      setLoadError("");
    } catch (err) {
      if (!silent) setLoadError(getErrorMessage(err, "Could not load documents"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while anything is still being processed
  const hasActive = docs.some((d) => ACTIVE.includes(d.processing_status));
  useEffect(() => {
    if (!hasActive) return;
    const t = setInterval(() => load(true), 2000);
    return () => clearInterval(t);
  }, [hasActive, load]);

  /* --------------------------------- Upload --------------------------------- */
  const uploadFiles = useCallback(
    async (files) => {
      setActionError("");
      for (const file of files) {
        const key = `${file.name}-${Date.now()}-${Math.random()}`;
        const problem = validateDocument(file);
        if (problem) {
          setUploads((u) => [...u, { key, name: file.name, progress: 0, error: problem }]);
          continue;
        }
        setUploads((u) => [...u, { key, name: file.name, progress: 0 }]);
        try {
          await documentsApi.upload(file, (p) =>
            setUploads((u) => u.map((x) => (x.key === key ? { ...x, progress: p } : x)))
          );
          setUploads((u) => u.filter((x) => x.key !== key));
          await load(true);
        } catch (err) {
          setUploads((u) =>
            u.map((x) => (x.key === key ? { ...x, error: getErrorMessage(err, "Upload failed") } : x))
          );
        }
      }
    },
    [load]
  );

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files || []);
    if (files.length) uploadFiles(files);
  };

  const onPick = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length) uploadFiles(files);
    e.target.value = "";
  };

  /* --------------------------------- Delete --------------------------------- */
  const remove = async (id) => {
    setDeletingId(id);
    setActionError("");
    try {
      await documentsApi.remove(id);
      setDocs((d) => d.filter((x) => x.id !== id));
    } catch (err) {
      setActionError(getErrorMessage(err, "Could not delete the document"));
    } finally {
      setDeletingId(null);
      setConfirmId(null);
    }
  };

  const ready = docs.filter((d) => d.processing_status === "completed").length;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8">
        <div className="mb-6 flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <button className="btn-ghost !p-2 md:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open sidebar">
              <Menu size={20} />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-zinc-50">Knowledge Base</h1>
              <p className="mt-1 text-sm text-zinc-400">
                Upload documents so Aria can answer questions using your own content.
                {docs.length > 0 && ` ${ready} of ${docs.length} ready.`}
              </p>
            </div>
          </div>
          <button className="btn-primary flex-none" onClick={() => fileRef.current?.click()}>
            <Upload size={16} /> <span className="hidden sm:inline">Upload document</span>
            <span className="sm:hidden">Upload</span>
          </button>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={ACCEPTED_DOC_TYPES.join(",")}
            className="hidden"
            onChange={onPick}
          />
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && fileRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors ${
            dragging ? "border-accent bg-accent-soft" : "border-ink-600 bg-ink-850 hover:border-ink-500"
          }`}
        >
          <Upload size={26} className={dragging ? "text-accent" : "text-zinc-500"} />
          <p className="mt-3 text-sm font-medium text-zinc-200">Drag and drop files here, or click to browse</p>
          <p className="mt-1 text-xs text-zinc-500">
            {ACCEPTED_DOC_TYPES.join(", ").toUpperCase().replaceAll(".", "")} · up to {MAX_UPLOAD_MB} MB each
          </p>
        </div>

        {/* In-flight uploads */}
        {uploads.length > 0 && (
          <ul className="mt-4 space-y-2">
            {uploads.map((u) => (
              <li key={u.key} className="card p-3">
                <div className="flex items-center gap-2 text-sm">
                  <FileText size={15} className="text-zinc-500" />
                  <span className="min-w-0 flex-1 truncate text-zinc-200">{u.name}</span>
                  {u.error ? (
                    <button
                      onClick={() => setUploads((x) => x.filter((i) => i.key !== u.key))}
                      aria-label="Dismiss"
                      className="text-zinc-500 hover:text-zinc-200"
                    >
                      <X size={14} />
                    </button>
                  ) : (
                    <span className="text-xs tabular-nums text-zinc-400">
                      {u.progress < 100 ? `${u.progress}%` : "Processing…"}
                    </span>
                  )}
                </div>
                {u.error ? (
                  <p className="mt-1.5 text-xs text-red-400">{u.error}</p>
                ) : (
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink-700">
                    <div
                      className="h-full rounded-full bg-accent transition-all"
                      style={{ width: `${Math.max(u.progress, 4)}%` }}
                    />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

        {actionError && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300" role="alert">
            <AlertCircle size={14} /> <span className="flex-1">{actionError}</span>
            <button onClick={() => setActionError("")} aria-label="Dismiss">
              <X size={14} />
            </button>
          </div>
        )}

        {/* Document list */}
        <div className="mt-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-zinc-300">Your documents</h2>
            <button className="btn-ghost !py-1 text-xs" onClick={() => load()}>
              <RefreshCw size={13} /> Refresh
            </button>
          </div>

          {loading ? (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-xl bg-ink-850" />
              ))}
            </div>
          ) : loadError ? (
            <div className="card p-6 text-center text-sm text-red-300">{loadError}</div>
          ) : docs.length === 0 ? (
            <div className="card flex flex-col items-center px-4 py-10 text-center">
              <FileText size={28} className="text-zinc-600" />
              <p className="mt-3 text-sm text-zinc-300">No documents yet</p>
              <p className="mt-1 text-xs text-zinc-500">Upload a PDF, DOCX, TXT or Markdown file to get started.</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {docs.map((d) => (
                <li key={d.id} className="card p-3 sm:p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 flex-none items-center justify-center rounded-lg bg-ink-700 text-[10px] font-semibold uppercase text-zinc-300">
                      {d.file_type}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-zinc-100" title={d.filename}>
                        {d.filename}
                      </p>
                      <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-zinc-500">
                        <span>{formatBytes(d.file_size)}</span>
                        <span>·</span>
                        <span>{formatDateTime(d.uploaded_at)}</span>
                        {d.processing_status === "completed" && (
                          <>
                            <span>·</span>
                            <span>{d.chunk_count} chunks</span>
                          </>
                        )}
                      </p>
                    </div>

                    <StatusBadge doc={d} />

                    {confirmId === d.id ? (
                      <div className="flex items-center gap-1">
                        <button
                          className="btn-ghost !p-1.5 text-red-400"
                          onClick={() => remove(d.id)}
                          disabled={deletingId === d.id}
                          aria-label="Confirm delete"
                        >
                          {deletingId === d.id ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
                        </button>
                        <button className="btn-ghost !p-1.5" onClick={() => setConfirmId(null)} aria-label="Cancel">
                          <X size={15} />
                        </button>
                      </div>
                    ) : (
                      <button
                        className="btn-ghost !p-1.5"
                        onClick={() => setConfirmId(d.id)}
                        aria-label={`Delete ${d.filename}`}
                        title="Delete document and its embeddings"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>

                  {ACTIVE.includes(d.processing_status) && (
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-700">
                      <div
                        className="h-full rounded-full bg-accent transition-all duration-500"
                        style={{ width: `${Math.max(d.progress ?? 8, 8)}%` }}
                      />
                    </div>
                  )}
                  {d.processing_status === "failed" && d.error && (
                    <p className="mt-2 text-xs text-red-400">{d.error}</p>
                  )}
                  {confirmId === d.id && (
                    <p className="mt-2 text-xs text-zinc-500">
                      This permanently deletes the file and all of its embeddings.
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
