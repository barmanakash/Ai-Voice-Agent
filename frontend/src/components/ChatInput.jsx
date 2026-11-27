import { useEffect, useRef } from "react";
import {
  ArrowUp,
  BookOpen,
  Headphones,
  Loader2,
  Mic,
  Paperclip,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { ACCEPTED_DOC_TYPES } from "../utils/format.js";

const STATE_LABEL = {
  listening: "Listening… click the mic to finish",
  transcribing: "Transcribing your speech…",
  thinking: "Thinking…",
  speaking: "Speaking…",
};

function fmt(sec) {
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  onStop,
  generating,
  onAttach,
  voice, // { state, mode, onToggleMode, onMic, seconds, supported, onStopSpeaking }
}) {
  const { prefs, updatePrefs } = useApp();
  const textareaRef = useRef(null);
  const fileRef = useRef(null);

  // Auto-grow the textarea up to a limit
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  const busyVoice = voice.state !== "idle";
  const canSend = value.trim().length > 0 && !generating && !busyVoice;

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (canSend) onSend();
    }
  };

  const handleFiles = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length) onAttach(files);
    e.target.value = "";
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-3 pb-3 sm:px-4 sm:pb-4">
      {/* Voice state pill */}
      {busyVoice && (
        <div
          className="mb-2 flex items-center justify-between rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 text-xs text-zinc-300"
          role="status"
          aria-live="polite"
        >
          <span className="flex items-center gap-2">
            {voice.state === "listening" ? (
              <span className="h-2 w-2 rounded-full bg-red-500 animate-pulseRing" />
            ) : (
              <Loader2 size={13} className="animate-spin text-accent" />
            )}
            {STATE_LABEL[voice.state]}
            {voice.state === "listening" && <span className="tabular-nums text-zinc-500">{fmt(voice.seconds)}</span>}
          </span>
          {voice.state === "speaking" && (
            <button onClick={voice.onStopSpeaking} className="text-zinc-400 underline hover:text-zinc-100">
              Stop
            </button>
          )}
        </div>
      )}

      <div className="rounded-2xl border border-ink-600 bg-ink-850 p-2 shadow-lg shadow-black/20 focus-within:border-accent/60">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder={
            voice.mode ? "Voice mode on — click the mic and speak, or type here…" : "Message Aria…"
          }
          aria-label="Message"
          className="max-h-[200px] w-full resize-none bg-transparent px-2 py-2 text-[15px] text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
        />

        <div className="flex items-center justify-between gap-2 pt-1">
          <div className="flex items-center gap-0.5">
            <input
              ref={fileRef}
              type="file"
              multiple
              accept={ACCEPTED_DOC_TYPES.join(",")}
              onChange={handleFiles}
              className="hidden"
            />
            <button
              className="btn-ghost !p-2"
              onClick={() => fileRef.current?.click()}
              title="Add a document to the knowledge base"
              aria-label="Attach document"
            >
              <Paperclip size={18} />
            </button>

            <button
              className={`btn-ghost !p-2 ${prefs.useKnowledgeBase ? "!text-accent" : ""}`}
              onClick={() => updatePrefs({ useKnowledgeBase: !prefs.useKnowledgeBase })}
              title={prefs.useKnowledgeBase ? "Knowledge base: ON" : "Knowledge base: OFF"}
              aria-pressed={prefs.useKnowledgeBase}
              aria-label="Toggle knowledge base"
            >
              <BookOpen size={18} />
            </button>

            <button
              className={`btn-ghost !p-2 ${voice.mode ? "!bg-accent-soft !text-accent" : ""}`}
              onClick={voice.onToggleMode}
              title={voice.mode ? "Voice conversation mode: ON" : "Voice conversation mode: OFF"}
              aria-pressed={voice.mode}
              aria-label="Toggle voice conversation mode"
            >
              <Headphones size={18} />
            </button>

            <button
              className="btn-ghost !p-2"
              onClick={() => updatePrefs({ ttsMuted: !prefs.ttsMuted })}
              title={prefs.ttsMuted ? "Unmute speech" : "Mute speech"}
              aria-pressed={prefs.ttsMuted}
              aria-label="Mute speech"
            >
              {prefs.ttsMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
            </button>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={voice.onMic}
              disabled={!voice.supported || (busyVoice && voice.state !== "listening") || generating}
              className={`flex h-9 w-9 items-center justify-center rounded-full transition-colors disabled:opacity-40 ${
                voice.state === "listening"
                  ? "bg-red-500 text-white animate-pulseRing"
                  : "text-zinc-300 hover:bg-ink-700"
              }`}
              title={
                !voice.supported
                  ? "Microphone not supported in this browser"
                  : voice.state === "listening"
                  ? "Stop recording"
                  : "Record voice message"
              }
              aria-label={voice.state === "listening" ? "Stop recording" : "Start recording"}
            >
              {voice.state === "listening" ? <Square size={15} fill="currentColor" /> : <Mic size={18} />}
            </button>

            {generating ? (
              <button
                onClick={onStop}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-100 text-ink-900 hover:bg-white"
                title="Stop generating"
                aria-label="Stop generating"
              >
                <Square size={14} fill="currentColor" />
              </button>
            ) : (
              <button
                onClick={onSend}
                disabled={!canSend}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-white transition-colors hover:bg-accent-hover disabled:bg-ink-600 disabled:text-zinc-500"
                title="Send message"
                aria-label="Send message"
              >
                <ArrowUp size={18} />
              </button>
            )}
          </div>
        </div>
      </div>

      <p className="mt-2 text-center text-[11px] text-zinc-600">
        Runs locally with Ollama. AI can make mistakes — verify important information.
      </p>
    </div>
  );
}
