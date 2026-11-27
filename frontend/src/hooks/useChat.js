import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { conversationsApi, streamChat, getErrorMessage } from "../services/api.js";
import { useApp } from "../context/AppContext.jsx";

let tmpCounter = 0;
const tmpId = (p) => `${p}-${Date.now()}-${tmpCounter++}`;

/**
 * Owns all chat state for the currently open conversation:
 * history loading, streaming, stop, regenerate and clear.
 */
export function useChat(conversationId) {
  const navigate = useNavigate();
  const { upsertConversation, refreshConversations, prefs } = useApp();

  const [messages, setMessages] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const abortRef = useRef(null);
  const activeIdRef = useRef(conversationId || null);
  const skipLoadRef = useRef(null); // id we just created while streaming; don't reload it
  const messagesRef = useRef([]);
  messagesRef.current = messages;

  /* ------------------------- Load history on route change ------------------------- */
  useEffect(() => {
    activeIdRef.current = conversationId || null;

    // We just created this conversation ourselves and are mid-stream.
    if (conversationId && skipLoadRef.current === conversationId) {
      skipLoadRef.current = null;
      return;
    }

    abortRef.current?.abort();
    setError("");
    setGenerating(false);

    if (!conversationId) {
      setMessages([]);
      return;
    }

    let cancelled = false;
    setLoadingHistory(true);
    conversationsApi
      .get(conversationId)
      .then((data) => {
        if (!cancelled) setMessages(data.messages || []);
      })
      .catch((err) => {
        if (cancelled) return;
        setMessages([]);
        setError(getErrorMessage(err, "Could not load this conversation"));
        if (err?.response?.status === 404) navigate("/", { replace: true });
      })
      .finally(() => !cancelled && setLoadingHistory(false));

    return () => {
      cancelled = true;
    };
  }, [conversationId, navigate]);

  // Abort any in-flight stream when the component unmounts.
  useEffect(() => () => abortRef.current?.abort(), []);

  /* ------------------------------- Core streaming ------------------------------- */
  const run = useCallback(
    async (text, { regenerate = false } = {}) => {
      setError("");
      setGenerating(true);

      const assistantTmp = tmpId("a");
      const userTmp = tmpId("u");

      setMessages((prev) => {
        let base = prev;
        if (regenerate) {
          // drop the last assistant message; keep the user message that prompted it
          const lastIdx = [...prev].map((m) => m.role).lastIndexOf("assistant");
          base = lastIdx >= 0 ? prev.filter((_, i) => i !== lastIdx) : prev;
        } else {
          base = [
            ...prev,
            { id: userTmp, role: "user", content: text, created_at: new Date().toISOString() },
          ];
        }
        return [
          ...base,
          { id: assistantTmp, role: "assistant", content: "", sources: [], streaming: true },
        ];
      });

      const patchAssistant = (patch) =>
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantTmp ? { ...m, ...(typeof patch === "function" ? patch(m) : patch) } : m))
        );

      const controller = new AbortController();
      abortRef.current = controller;
      let acc = "";
      let failed = false;

      try {
        await streamChat(
          {
            conversation_id: activeIdRef.current,
            message: text,
            use_knowledge_base: prefs.useKnowledgeBase,
            regenerate,
          },
          {
            onMeta: (evt) => {
              if (evt.conversation_id && evt.conversation_id !== activeIdRef.current) {
                activeIdRef.current = evt.conversation_id;
                skipLoadRef.current = evt.conversation_id;
                navigate(`/c/${evt.conversation_id}`, { replace: true });
              }
              if (evt.conversation_id) {
                upsertConversation({
                  id: evt.conversation_id,
                  title: evt.title || "New chat",
                  updated_at: new Date().toISOString(),
                  created_at: new Date().toISOString(),
                });
              }
              if (evt.user_message_id && !regenerate) {
                setMessages((prev) => prev.map((m) => (m.id === userTmp ? { ...m, id: evt.user_message_id } : m)));
              }
            },
            onSources: (sources) => patchAssistant({ sources }),
            onToken: (chunk) => {
              acc += chunk;
              patchAssistant((m) => ({ content: m.content + chunk }));
            },
            onDone: (evt) =>
              patchAssistant({
                id: evt.message_id || assistantTmp,
                streaming: false,
                usedKnowledgeBase: !!evt.used_knowledge_base,
              }),
            onError: (detail) => {
              failed = true;
              setError(detail);
              patchAssistant({ streaming: false, failed: true });
            },
          },
          controller.signal
        );
      } catch (err) {
        if (err?.name === "AbortError") {
          // user pressed Stop: keep whatever text arrived
          patchAssistant({ streaming: false, stopped: true });
        } else {
          failed = true;
          setError(getErrorMessage(err));
          patchAssistant({ streaming: false, failed: true });
        }
      } finally {
        // Remove an assistant bubble that never received anything
        setMessages((prev) => prev.filter((m) => !(m.id === assistantTmp && !m.content && !m.sources?.length)));
        setGenerating(false);
        abortRef.current = null;
        refreshConversations();
      }

      return failed ? null : acc;
    },
    [navigate, prefs.useKnowledgeBase, refreshConversations, upsertConversation]
  );

  /* -------------------------------- Public actions ------------------------------- */
  const sendMessage = useCallback(
    (text) => {
      const trimmed = text.trim();
      if (!trimmed || generating) return Promise.resolve(null);
      return run(trimmed);
    },
    [generating, run]
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const regenerate = useCallback(() => {
    if (generating) return Promise.resolve(null);
    const lastUser = [...messagesRef.current].reverse().find((m) => m.role === "user");
    if (!lastUser) return Promise.resolve(null);
    return run(lastUser.content, { regenerate: true });
  }, [generating, run]);

  const clear = useCallback(async () => {
    if (!activeIdRef.current) {
      setMessages([]);
      return;
    }
    try {
      await conversationsApi.clear(activeIdRef.current);
      setMessages([]);
      setError("");
    } catch (err) {
      setError(getErrorMessage(err, "Could not clear the conversation"));
    }
  }, []);

  return {
    messages,
    loadingHistory,
    generating,
    error,
    setError,
    sendMessage,
    stop,
    regenerate,
    clear,
  };
}
