import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertCircle, Check, Eraser, Loader2, X } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { useChat } from "../hooks/useChat.js";
import { useRecorder } from "../hooks/useRecorder.js";
import { useAudioPlayer } from "../hooks/useAudioPlayer.js";
import { documentsApi, voiceApi, getErrorMessage } from "../services/api.js";
import { validateDocument } from "../utils/format.js";
import ChatInput from "../components/ChatInput.jsx";
import MessageBubble from "../components/MessageBubble.jsx";
import WelcomeScreen from "../components/WelcomeScreen.jsx";

let noticeId = 0;

export default function ChatPage() {
  const { conversationId } = useParams();
  const { conversations, prefs } = useApp();

  const chat = useChat(conversationId);
  const recorder = useRecorder();
  const player = useAudioPlayer();

  const [input, setInput] = useState("");
  const [voiceMode, setVoiceMode] = useState(false);
  const [voiceState, setVoiceState] = useState("idle"); // idle | listening | transcribing | thinking | speaking
  const [voiceError, setVoiceError] = useState("");
  const [notices, setNotices] = useState([]);
  const [confirmClear, setConfirmClear] = useState(false);

  const scrollRef = useRef(null);
  const stickRef = useRef(true);
  const mountedRef = useRef(true);
  const voiceModeRef = useRef(voiceMode);
  voiceModeRef.current = voiceMode;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const title = useMemo(
    () => conversations.find((c) => c.id === conversationId)?.title,
    [conversations, conversationId]
  );

  /* --------------------------------- Scrolling -------------------------------- */
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [chat.messages]);

  // Jump to the bottom when switching conversations
  useEffect(() => {
    stickRef.current = true;
    setConfirmClear(false);
  }, [conversationId]);

  /* ------------------------------ Notices (toasts) ----------------------------- */
  const pushNotice = useCallback((type, text) => {
    const id = ++noticeId;
    setNotices((n) => [...n, { id, type, text }]);
    if (type !== "error") setTimeout(() => setNotices((n) => n.filter((x) => x.id !== id)), 6000);
    return id;
  }, []);
  const dismissNotice = (id) => setNotices((n) => n.filter((x) => x.id !== id));

  /* --------------------------------- Sending --------------------------------- */
  const handleSend = useCallback(
    async (textOverride) => {
      const text = (textOverride ?? input).trim();
      if (!text) return null;
      setInput("");
      stickRef.current = true;
      return chat.sendMessage(text);
    },
    [chat, input]
  );

  /* -------------------------------- Voice flow -------------------------------- */
  const startListening = useCallback(async () => {
    setVoiceError("");
    player.stop();
    const ok = await recorder.start();
    if (ok) setVoiceState("listening");
    return ok;
  }, [player, recorder]);

  const finishListening = useCallback(async () => {
    const blob = await recorder.stop();
    if (!blob) {
      setVoiceState("idle");
      setVoiceError("No audio was captured. Please try again.");
      return;
    }

    setVoiceState("transcribing");
    let text = "";
    try {
      const res = await voiceApi.transcribe(blob);
      text = (res.text || "").trim();
    } catch (err) {
      setVoiceError(getErrorMessage(err, "Transcription failed"));
      setVoiceState("idle");
      return;
    }
    if (!mountedRef.current) return;

    if (!text) {
      setVoiceError("I couldn't hear any speech. Please try again.");
      setVoiceState("idle");
      return;
    }

    // Normal mic: show the transcription so the user can edit it before sending.
    if (!voiceModeRef.current) {
      setInput((prev) => (prev ? `${prev} ${text}` : text));
      setVoiceState("idle");
      return;
    }

    // Voice conversation mode: send, then speak the answer.
    setVoiceState("thinking");
    stickRef.current = true;
    const answer = await chat.sendMessage(text);
    if (!mountedRef.current) return;

    if (answer && prefs.autoSpeak && !prefs.ttsMuted) {
      setVoiceState("speaking");
      await player.speak(`voice-${Date.now()}`, answer);
    }
    if (!mountedRef.current) return;
    setVoiceState("idle");

    // Only re-open the mic when the user explicitly enabled continuous mode.
    if (answer && prefs.continuousMode && voiceModeRef.current) {
      startListening();
    }
  }, [chat, player, prefs.autoSpeak, prefs.continuousMode, prefs.ttsMuted, recorder, startListening]);

  const handleMic = useCallback(() => {
    if (voiceState === "listening") finishListening();
    else if (voiceState === "idle") startListening();
  }, [finishListening, startListening, voiceState]);

  const toggleVoiceMode = () => {
    setVoiceMode((v) => !v);
    if (voiceState === "listening") {
      recorder.cancel();
      setVoiceState("idle");
    }
  };

  const stopSpeaking = () => {
    player.stop();
    setVoiceState("idle");
  };

  // Stop button while generating also ends the voice "thinking" state
  const handleStop = () => {
    chat.stop();
  };

  /* ---------------------------- Attachments (to KB) ---------------------------- */
  const handleAttach = useCallback(
    async (files) => {
      for (const file of files) {
        const problem = validateDocument(file);
        if (problem) {
          pushNotice("error", problem);
          continue;
        }
        const id = pushNotice("progress", `Uploading ${file.name}…`);
        try {
          await documentsApi.upload(file);
          dismissNotice(id);
          pushNotice("success", `${file.name} added to your knowledge base and is being processed.`);
        } catch (err) {
          dismissNotice(id);
          pushNotice("error", `${file.name}: ${getErrorMessage(err, "Upload failed")}`);
        }
      }
    },
    [pushNotice]
  );

  const handleClear = async () => {
    setConfirmClear(false);
    await chat.clear();
  };

  /* ---------------------------------- Render ---------------------------------- */
  const hasMessages = chat.messages.length > 0;
  const errors = [chat.error, voiceError, recorder.error, player.error].filter(Boolean);
  const dismissErrors = () => {
    chat.setError("");
    setVoiceError("");
    recorder.setError("");
    player.setError("");
  };

  return (
    <div className="flex h-full flex-col">
      {/* Top bar (desktop) */}
      <div className="hidden items-center justify-between border-b border-ink-700 px-5 py-2.5 md:flex">
        <h2 className="truncate text-sm font-medium text-zinc-300">{title || "New chat"}</h2>
        {hasMessages && conversationId && (
          <div className="flex items-center gap-2">
            {confirmClear ? (
              <>
                <span className="text-xs text-zinc-400">Clear all messages?</span>
                <button className="btn-ghost !p-1.5 text-red-400" onClick={handleClear} aria-label="Confirm clear">
                  <Check size={15} />
                </button>
                <button className="btn-ghost !p-1.5" onClick={() => setConfirmClear(false)} aria-label="Cancel clear">
                  <X size={15} />
                </button>
              </>
            ) : (
              <button className="btn-ghost !py-1.5 text-xs" onClick={() => setConfirmClear(true)}>
                <Eraser size={14} /> Clear history
              </button>
            )}
          </div>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} onScroll={onScroll} className="min-h-0 flex-1 overflow-y-auto">
        {chat.loadingHistory ? (
          <div className="flex h-full items-center justify-center text-zinc-500">
            <Loader2 className="animate-spin" size={22} />
          </div>
        ) : !hasMessages ? (
          <WelcomeScreen onPick={(t) => setInput(t)} />
        ) : (
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
            {chat.messages.map((m, i) => (
              <MessageBubble
                key={m.id}
                message={m}
                isLast={i === chat.messages.length - 1}
                generating={chat.generating}
                onRegenerate={chat.regenerate}
                player={player}
                muted={prefs.ttsMuted}
              />
            ))}
          </div>
        )}
      </div>

      {/* Notices + errors */}
      <div className="mx-auto w-full max-w-3xl space-y-2 px-3 sm:px-4">
        {notices.map((n) => (
          <div
            key={n.id}
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
              n.type === "error"
                ? "border-red-500/30 bg-red-500/10 text-red-300"
                : n.type === "success"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : "border-ink-600 bg-ink-850 text-zinc-300"
            }`}
          >
            {n.type === "progress" && <Loader2 size={13} className="animate-spin" />}
            <span className="flex-1">{n.text}</span>
            {n.type === "success" && (
              <Link to="/knowledge-base" className="underline">
                View
              </Link>
            )}
            <button onClick={() => dismissNotice(n.id)} aria-label="Dismiss" className="opacity-70 hover:opacity-100">
              <X size={13} />
            </button>
          </div>
        ))}

        {errors.length > 0 && (
          <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300" role="alert">
            <AlertCircle size={14} className="mt-0.5 flex-none" />
            <div className="flex-1 space-y-0.5">
              {errors.map((e, i) => (
                <p key={i}>{e}</p>
              ))}
            </div>
            <button onClick={dismissErrors} aria-label="Dismiss error" className="opacity-70 hover:opacity-100">
              <X size={14} />
            </button>
          </div>
        )}
      </div>

      <ChatInput
        value={input}
        onChange={setInput}
        onSend={() => handleSend()}
        onStop={handleStop}
        generating={chat.generating}
        onAttach={handleAttach}
        voice={{
          state: voiceState,
          mode: voiceMode,
          onToggleMode: toggleVoiceMode,
          onMic: handleMic,
          seconds: recorder.seconds,
          supported: recorder.supported,
          onStopSpeaking: stopSpeaking,
        }}
      />
    </div>
  );
}
