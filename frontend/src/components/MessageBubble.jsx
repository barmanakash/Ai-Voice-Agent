import { useState } from "react";
import {
  AlertCircle,
  AudioLines,
  Check,
  Copy,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Sparkles,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer.jsx";
import SourceCitations from "./SourceCitations.jsx";
import TypingIndicator from "./TypingIndicator.jsx";

function IconButton({ label, onClick, disabled, children }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-ink-700 hover:text-zinc-100 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  );
}

export default function MessageBubble({ message, isLast, generating, onRegenerate, player, muted }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end animate-fadeUp">
        <div className="group max-w-[85%] sm:max-w-[75%]">
          <div className="whitespace-pre-wrap rounded-2xl rounded-br-md bg-ink-700 px-4 py-2.5 text-[15px] leading-7 text-zinc-100">
            {message.content}
          </div>
          <div className="mt-1 flex justify-end opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
            <IconButton label={copied ? "Copied" : "Copy message"} onClick={copy}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </IconButton>
          </div>
        </div>
      </div>
    );
  }

  const isActiveAudio = player.activeId === message.id;
  const showTyping = message.streaming && !message.content;
  const hasSources = message.sources?.length > 0;
  const fromKb = message.usedKnowledgeBase ?? hasSources;
  const done = !message.streaming && !!message.content;

  return (
    <div className="flex gap-3 animate-fadeUp">
      <div className="mt-1 flex h-8 w-8 flex-none items-center justify-center rounded-full bg-accent-soft text-accent">
        <Sparkles size={16} />
      </div>

      <div className="min-w-0 flex-1">
        {showTyping ? (
          <TypingIndicator />
        ) : (
          <>
            <MarkdownRenderer content={message.content} />
            {message.streaming && (
              <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-accent" />
            )}
          </>
        )}

        {done && (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${
                fromKb ? "bg-accent-soft text-accent" : "bg-ink-700 text-zinc-400"
              }`}
            >
              {fromKb ? "From your knowledge base" : "General AI answer"}
            </span>
            {message.stopped && <span className="text-zinc-500">Generation stopped</span>}
          </div>
        )}

        {message.failed && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-red-400">
            <AlertCircle size={13} /> This response did not finish.
          </div>
        )}

        {fromKb && <SourceCitations sources={message.sources} />}

        {done && (
          <div className="mt-2 flex items-center gap-0.5">
            <IconButton label={copied ? "Copied" : "Copy message"} onClick={copy}>
              {copied ? <Check size={15} /> : <Copy size={15} />}
            </IconButton>

            {/* Text-to-speech controls */}
            {muted ? (
              <IconButton label="Speech is muted" disabled>
                <VolumeX size={15} />
              </IconButton>
            ) : isActiveAudio && player.status === "loading" ? (
              <IconButton label="Generating speech…" disabled>
                <Loader2 size={15} className="animate-spin" />
              </IconButton>
            ) : isActiveAudio && player.status === "playing" ? (
              <>
                <IconButton label="Pause" onClick={player.pause}>
                  <Pause size={15} />
                </IconButton>
                <IconButton label="Stop" onClick={player.stop}>
                  <Square size={15} />
                </IconButton>
              </>
            ) : isActiveAudio && player.status === "paused" ? (
              <>
                <IconButton label="Resume" onClick={player.resume}>
                  <Play size={15} />
                </IconButton>
                <IconButton label="Stop" onClick={player.stop}>
                  <Square size={15} />
                </IconButton>
              </>
            ) : (
              <>
                <IconButton label="Read aloud" onClick={() => player.speak(message.id, message.content)}>
                  <Volume2 size={15} />
                </IconButton>
                <IconButton
                  label="Regenerate speech"
                  onClick={() => player.speak(message.id, message.content, { force: true })}
                >
                  <AudioLines size={15} />
                </IconButton>
              </>
            )}

            {isLast && (
              <IconButton label="Regenerate response" onClick={onRegenerate} disabled={generating}>
                <RefreshCw size={15} />
              </IconButton>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
