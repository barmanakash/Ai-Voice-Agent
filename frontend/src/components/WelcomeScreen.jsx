import { BookOpen, Code2, Lightbulb, Mic, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "../context/AppContext.jsx";

const SUGGESTIONS = [
  { icon: BookOpen, title: "Ask my documents", text: "Summarize the key points from my uploaded documents." },
  { icon: Code2, title: "Write some code", text: "Write a Python function that removes duplicates from a list and explain it." },
  { icon: Lightbulb, title: "Explain a concept", text: "Explain how retrieval-augmented generation works in simple terms." },
  { icon: Mic, title: "Try voice mode", text: "Give me three quick tips for staying focused while studying." },
];

export default function WelcomeScreen({ onPick }) {
  const { modelStatus } = useApp();
  const problem = modelStatus.state === "offline" || modelStatus.state === "model_missing";

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col items-center justify-center px-4 py-10 text-center">
      <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-accent">
        <Sparkles size={28} />
      </div>
      <h1 className="text-2xl font-semibold text-zinc-50 sm:text-3xl">How can I help you today?</h1>
      <p className="mt-2 max-w-md text-sm text-zinc-400">
        Aria runs fully on your computer. Chat by text or voice and ground answers in your own documents.
      </p>

      {problem && (
        <div className="mt-6 w-full max-w-lg rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-left text-sm text-amber-200">
          <p className="font-medium">
            {modelStatus.state === "offline" ? "Can't reach Ollama" : "Model not installed"}
          </p>
          <p className="mt-1 text-amber-200/80">{modelStatus.message}</p>
          <Link to="/settings" className="mt-2 inline-block text-xs underline underline-offset-2">
            Open settings
          </Link>
        </div>
      )}

      <div className="mt-8 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map(({ icon: Icon, title, text }) => (
          <button
            key={title}
            onClick={() => onPick(text)}
            className="card group p-4 text-left transition-colors hover:border-accent/50 hover:bg-ink-800"
          >
            <Icon size={18} className="mb-2 text-accent" />
            <div className="text-sm font-medium text-zinc-100">{title}</div>
            <div className="mt-0.5 line-clamp-2 text-xs text-zinc-500">{text}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
