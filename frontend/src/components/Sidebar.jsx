import { useMemo, useState } from "react";
import { NavLink, useMatch, useNavigate } from "react-router-dom";
import {
  AudioLines,
  Check,
  Database,
  Loader2,
  MessageSquarePlus,
  Pencil,
  Search,
  Settings,
  Trash2,
  X,
} from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { groupConversations } from "../utils/format.js";
import { getErrorMessage } from "../services/api.js";
import ModelStatusBadge from "./ModelStatusBadge.jsx";

function ConversationItem({ conv, active, onOpen }) {
  const { renameConversation, removeConversation } = useApp();
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(conv.title);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const saveRename = async () => {
    const next = title.trim();
    if (!next || next === conv.title) {
      setEditing(false);
      setTitle(conv.title);
      return;
    }
    setBusy(true);
    try {
      await renameConversation(conv.id, next);
      setEditing(false);
    } catch (err) {
      setError(getErrorMessage(err, "Rename failed"));
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = async () => {
    setBusy(true);
    try {
      await removeConversation(conv.id);
      if (active) navigate("/", { replace: true });
    } catch (err) {
      setError(getErrorMessage(err, "Delete failed"));
      setBusy(false);
      setConfirming(false);
    }
  };

  if (editing) {
    return (
      <div className="flex items-center gap-1 px-1">
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") saveRename();
            if (e.key === "Escape") {
              setEditing(false);
              setTitle(conv.title);
            }
          }}
          maxLength={80}
          className="input !py-1.5"
          aria-label="Conversation title"
        />
        <button className="btn-ghost !p-1.5" onClick={saveRename} disabled={busy} aria-label="Save title">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
        </button>
      </div>
    );
  }

  if (confirming) {
    return (
      <div className="flex items-center justify-between gap-1 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-300">
        <span>Delete this chat?</span>
        <span className="flex gap-1">
          <button className="rounded p-1 hover:bg-red-500/20" onClick={confirmDelete} disabled={busy} aria-label="Confirm delete">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          </button>
          <button className="rounded p-1 hover:bg-red-500/20" onClick={() => setConfirming(false)} aria-label="Cancel delete">
            <X size={14} />
          </button>
        </span>
      </div>
    );
  }

  return (
    <div>
      <div
        className={`group flex items-center rounded-lg transition-colors ${
          active ? "bg-ink-700 text-zinc-50" : "text-zinc-400 hover:bg-ink-800 hover:text-zinc-200"
        }`}
      >
        <button onClick={() => onOpen(conv.id)} className="min-w-0 flex-1 truncate px-3 py-2 text-left text-sm">
          {conv.title || "New chat"}
        </button>
        <span className="mr-1 hidden gap-0.5 group-hover:flex group-focus-within:flex">
          <button className="rounded p-1.5 hover:bg-ink-600" onClick={() => setEditing(true)} aria-label="Rename conversation">
            <Pencil size={13} />
          </button>
          <button className="rounded p-1.5 hover:bg-ink-600" onClick={() => setConfirming(true)} aria-label="Delete conversation">
            <Trash2 size={13} />
          </button>
        </span>
      </div>
      {error && <p className="px-3 text-[11px] text-red-400">{error}</p>}
    </div>
  );
}

export default function Sidebar({ onNavigate }) {
  const { conversations, conversationsLoading, conversationsError } = useApp();
  const navigate = useNavigate();
  const conversationId = useMatch("/c/:conversationId")?.params.conversationId;
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? conversations.filter((c) => (c.title || "").toLowerCase().includes(q)) : conversations;
  }, [conversations, query]);

  const groups = useMemo(() => groupConversations(filtered), [filtered]);

  const go = (path) => {
    navigate(path);
    onNavigate?.();
  };

  const navClass = ({ isActive }) =>
    `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
      isActive ? "bg-ink-700 text-zinc-50" : "text-zinc-400 hover:bg-ink-800 hover:text-zinc-200"
    }`;

  return (
    <div className="flex h-full flex-col bg-ink-900">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 pb-3 pt-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-white">
          <AudioLines size={18} />
        </div>
        <div>
          <div className="text-sm font-semibold leading-tight text-zinc-50">Aria</div>
          <div className="text-[11px] leading-tight text-zinc-500">Local AI assistant</div>
        </div>
      </div>

      <div className="space-y-2 px-3">
        <button className="btn-outline w-full justify-start" onClick={() => go("/")}>
          <MessageSquarePlus size={16} /> New chat
        </button>
        <div className="relative">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats"
            aria-label="Search conversations"
            className="input !pl-8"
          />
        </div>
      </div>

      {/* Conversation list */}
      <div className="mt-3 min-h-0 flex-1 overflow-y-auto px-3 pb-2">
        {conversationsLoading ? (
          <div className="space-y-2 pt-1">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-8 animate-pulse rounded-lg bg-ink-800" />
            ))}
          </div>
        ) : conversationsError ? (
          <p className="px-1 pt-2 text-xs text-red-400">{conversationsError}</p>
        ) : groups.length === 0 ? (
          <p className="px-1 pt-3 text-xs text-zinc-500">
            {query ? "No chats match your search." : "No conversations yet. Start a new chat!"}
          </p>
        ) : (
          groups.map(([label, items]) => (
            <div key={label} className="mb-3">
              <div className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wide text-zinc-600">{label}</div>
              <div className="space-y-0.5">
                {items.map((c) => (
                  <ConversationItem
                    key={c.id}
                    conv={c}
                    active={c.id === conversationId}
                    onOpen={(id) => go(`/c/${id}`)}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer nav */}
      <div className="space-y-0.5 border-t border-ink-700 p-3">
        <NavLink to="/knowledge-base" className={navClass} onClick={onNavigate}>
          <Database size={16} /> Knowledge Base
        </NavLink>
        <NavLink to="/settings" className={navClass} onClick={onNavigate}>
          <Settings size={16} /> Settings
        </NavLink>
        <ModelStatusBadge />
      </div>
    </div>
  );
}
