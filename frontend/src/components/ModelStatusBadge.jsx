import { Link } from "react-router-dom";
import { useApp } from "../context/AppContext.jsx";

const STYLES = {
  checking: { dot: "bg-zinc-500 animate-pulse", label: "Checking model…" },
  ready: { dot: "bg-emerald-500", label: "" },
  model_missing: { dot: "bg-amber-500", label: "Model not installed" },
  offline: { dot: "bg-red-500", label: "Ollama offline" },
};

export default function ModelStatusBadge() {
  const { modelStatus } = useApp();
  const s = STYLES[modelStatus.state];
  const label = modelStatus.state === "ready" ? modelStatus.model : s.label;

  return (
    <Link
      to="/settings"
      title={modelStatus.message || "Model status"}
      className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-zinc-400 hover:bg-ink-700 hover:text-zinc-200"
    >
      <span className={`h-2 w-2 flex-none rounded-full ${s.dot}`} />
      <span className="truncate">{label}</span>
    </Link>
  );
}
