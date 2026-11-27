import { useState } from "react";
import { BookOpen, ChevronDown, FileText } from "lucide-react";

/**
 * Expandable list of knowledge-base sources used for an answer.
 * source: { document_id, document_name, chunk_id, page, score, snippet }
 */
export default function SourceCitations({ sources = [] }) {
  const [open, setOpen] = useState(false);
  if (!sources.length) return null;

  const names = [...new Set(sources.map((s) => s.document_name))];

  return (
    <div className="mt-3 rounded-lg border border-ink-700 bg-ink-850/60">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-zinc-400 hover:text-zinc-200"
        aria-expanded={open}
      >
        <BookOpen size={14} className="text-accent" />
        <span className="flex-1">
          Sources from knowledge base ({names.length} document{names.length === 1 ? "" : "s"})
        </span>
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <ul className="space-y-2 border-t border-ink-700 p-3">
          {sources.map((s, i) => (
            <li key={`${s.chunk_id}-${i}`} className="rounded-md bg-ink-800 p-2.5 text-xs">
              <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-zinc-300">
                <span className="flex h-4 w-4 items-center justify-center rounded bg-accent-soft text-[10px] font-semibold text-accent">
                  {i + 1}
                </span>
                <FileText size={12} className="text-zinc-500" />
                <span className="font-medium">{s.document_name}</span>
                {s.page != null && <span className="text-zinc-500">page {s.page}</span>}
                {typeof s.score === "number" && (
                  <span className="text-zinc-500">· relevance {(s.score * 100).toFixed(0)}%</span>
                )}
              </div>
              {s.snippet && <p className="line-clamp-3 text-zinc-500">{s.snippet}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
