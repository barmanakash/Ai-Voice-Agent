import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { conversationsApi, modelsApi, getErrorMessage } from "../services/api.js";

const AppContext = createContext(null);

const PREFS_KEY = "aria.prefs.v1";
const DEFAULT_PREFS = {
  useKnowledgeBase: true, // use RAG for chat
  ttsMuted: false,
  ttsVoice: "",
  autoSpeak: true, // speak the answer in voice mode
  continuousMode: false, // re-open the mic after the answer (explicit opt-in)
};

function loadPrefs() {
  try {
    return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(PREFS_KEY) || "{}") };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function AppProvider({ children }) {
  const [conversations, setConversations] = useState([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [conversationsError, setConversationsError] = useState("");

  const [modelStatus, setModelStatus] = useState({
    state: "checking", // checking | ready | model_missing | offline
    model: "",
    message: "",
  });

  const [prefs, setPrefs] = useState(loadPrefs);
  const [sidebarOpen, setSidebarOpen] = useState(false); // mobile drawer

  /* ------------------------------ Preferences ----------------------------- */
  const updatePrefs = useCallback((patch) => {
    setPrefs((prev) => {
      const next = { ...prev, ...patch };
      try {
        localStorage.setItem(PREFS_KEY, JSON.stringify(next));
      } catch {
        /* storage may be unavailable; preferences just won't persist */
      }
      return next;
    });
  }, []);

  /* ----------------------------- Conversations ---------------------------- */
  const refreshConversations = useCallback(async () => {
    try {
      const data = await conversationsApi.list();
      setConversations(data);
      setConversationsError("");
    } catch (err) {
      setConversationsError(getErrorMessage(err, "Could not load conversations"));
    } finally {
      setConversationsLoading(false);
    }
  }, []);

  const upsertConversation = useCallback((conv) => {
    setConversations((prev) => {
      const exists = prev.some((c) => c.id === conv.id);
      const next = exists ? prev.map((c) => (c.id === conv.id ? { ...c, ...conv } : c)) : [conv, ...prev];
      return [...next].sort(
        (a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at)
      );
    });
  }, []);

  const removeConversation = useCallback(async (id) => {
    await conversationsApi.remove(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
  }, []);

  const renameConversation = useCallback(
    async (id, title) => {
      const updated = await conversationsApi.rename(id, title);
      upsertConversation(updated);
    },
    [upsertConversation]
  );

  /* ------------------------------ Model status ---------------------------- */
  const refreshModelStatus = useCallback(async () => {
    try {
      const s = await modelsApi.status();
      if (!s.ollama_connected) {
        setModelStatus({ state: "offline", model: s.model || "", message: s.message || "Ollama is not running" });
      } else if (!s.model_available) {
        setModelStatus({
          state: "model_missing",
          model: s.model || "",
          message: s.message || `Model "${s.model}" is not installed. Run: ollama pull ${s.model}`,
        });
      } else {
        setModelStatus({ state: "ready", model: s.model, message: "" });
      }
    } catch (err) {
      setModelStatus({ state: "offline", model: "", message: getErrorMessage(err, "Backend unreachable") });
    }
  }, []);

  useEffect(() => {
    refreshConversations();
    refreshModelStatus();
    const timer = setInterval(refreshModelStatus, 30000);
    return () => clearInterval(timer);
  }, [refreshConversations, refreshModelStatus]);

  const value = useMemo(
    () => ({
      conversations,
      conversationsLoading,
      conversationsError,
      refreshConversations,
      upsertConversation,
      removeConversation,
      renameConversation,
      modelStatus,
      refreshModelStatus,
      prefs,
      updatePrefs,
      sidebarOpen,
      setSidebarOpen,
    }),
    [
      conversations,
      conversationsLoading,
      conversationsError,
      refreshConversations,
      upsertConversation,
      removeConversation,
      renameConversation,
      modelStatus,
      refreshModelStatus,
      prefs,
      updatePrefs,
      sidebarOpen,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside <AppProvider>");
  return ctx;
}
