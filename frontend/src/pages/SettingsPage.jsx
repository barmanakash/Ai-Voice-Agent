import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Check, Loader2, Menu, RefreshCw, Save, Volume2 } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { modelsApi, settingsApi, voiceApi, getErrorMessage } from "../services/api.js";
import { formatBytes } from "../utils/format.js";

const WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"];

function Section({ title, description, children }) {
  return (
    <section className="card p-4 sm:p-5">
      <h2 className="text-sm font-semibold text-zinc-100">{title}</h2>
      {description && <p className="mt-0.5 text-xs text-zinc-500">{description}</p>}
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-zinc-300">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-zinc-500">{hint}</span>}
    </label>
  );
}

function Toggle({ label, hint, checked, onChange }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <div className="text-sm text-zinc-200">{label}</div>
        {hint && <div className="text-[11px] text-zinc-500">{hint}</div>}
      </div>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 flex-none rounded-full transition-colors ${checked ? "bg-accent" : "bg-ink-600"}`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
            checked ? "translate-x-[22px]" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}

const STATUS_TEXT = {
  checking: { dot: "bg-zinc-500 animate-pulse", text: "Checking connection…" },
  ready: { dot: "bg-emerald-500", text: "Connected" },
  model_missing: { dot: "bg-amber-500", text: "Connected, but the selected model is not installed" },
  offline: { dot: "bg-red-500", text: "Ollama is not reachable" },
};

export default function SettingsPage() {
  const { modelStatus, refreshModelStatus, prefs, updatePrefs, setSidebarOpen } = useApp();

  const [settings, setSettings] = useState(null);
  const [initial, setInitial] = useState(null);
  const [models, setModels] = useState([]);
  const [voices, setVoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState(null); // {type, text}
  const [testing, setTesting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    const [s, m, v] = await Promise.allSettled([settingsApi.get(), modelsApi.list(), voiceApi.voices()]);

    if (s.status === "fulfilled") {
      setSettings(s.value);
      setInitial(s.value);
    } else {
      setLoadError(getErrorMessage(s.reason, "Could not load settings from the backend"));
    }
    if (m.status === "fulfilled") setModels(m.value.models || []);
    if (v.status === "fulfilled") setVoices(v.value.voices || []);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const set = (path, value) =>
    setSettings((prev) => {
      const next = structuredClone(prev);
      const keys = path.split(".");
      let ref = next;
      keys.slice(0, -1).forEach((k) => (ref = ref[k]));
      ref[keys.at(-1)] = value;
      return next;
    });

  const dirty = settings && JSON.stringify(settings) !== JSON.stringify(initial);

  const save = async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      const updated = await settingsApi.update(settings);
      setSettings(updated);
      setInitial(updated);
      setSaveMsg({ type: "success", text: "Settings saved." });
      refreshModelStatus();
    } catch (err) {
      setSaveMsg({ type: "error", text: getErrorMessage(err, "Could not save settings") });
    } finally {
      setSaving(false);
    }
  };

  const testVoice = async () => {
    setTesting(true);
    setSaveMsg(null);
    try {
      const blob = await voiceApi.speak("Hello! This is how I sound.", prefs.ttsVoice || undefined);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch (err) {
      setSaveMsg({ type: "error", text: getErrorMessage(err, "Could not play the voice sample") });
    } finally {
      setTesting(false);
    }
  };

  const status = STATUS_TEXT[modelStatus.state];
  const installed = models.map((m) => m.name);
  const currentMissing = settings && settings.model && !installed.includes(settings.model);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
        <div className="mb-6 flex items-start gap-2">
          <button className="btn-ghost !p-2 md:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open sidebar">
            <Menu size={20} />
          </button>
          <div>
            <h1 className="text-xl font-semibold text-zinc-50">Settings</h1>
            <p className="mt-1 text-sm text-zinc-400">Configure your local model, voice and knowledge base.</p>
          </div>
        </div>

        <div className="space-y-4">
          {/* Connection */}
          <Section title="Ollama connection">
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2.5">
                <span className={`h-2.5 w-2.5 flex-none rounded-full ${status.dot}`} />
                <div className="min-w-0">
                  <div className="text-sm text-zinc-200">{status.text}</div>
                  {modelStatus.message && <div className="text-xs text-zinc-500">{modelStatus.message}</div>}
                  {modelStatus.state === "ready" && (
                    <div className="text-xs text-zinc-500">Active model: {modelStatus.model}</div>
                  )}
                </div>
              </div>
              <button className="btn-outline flex-none" onClick={refreshModelStatus}>
                <RefreshCw size={14} /> Recheck
              </button>
            </div>
            {modelStatus.state === "offline" && (
              <pre className="overflow-x-auto rounded-lg bg-ink-900 p-3 font-mono text-xs text-zinc-300">
                {"ollama serve"}
              </pre>
            )}
            {modelStatus.state === "model_missing" && (
              <pre className="overflow-x-auto rounded-lg bg-ink-900 p-3 font-mono text-xs text-zinc-300">
                {`ollama pull ${modelStatus.model}`}
              </pre>
            )}
          </Section>

          {loading ? (
            <div className="flex justify-center py-10 text-zinc-500">
              <Loader2 className="animate-spin" size={22} />
            </div>
          ) : loadError ? (
            <div className="card flex items-start gap-2 p-4 text-sm text-red-300">
              <AlertCircle size={16} className="mt-0.5 flex-none" />
              <div>
                <p>{loadError}</p>
                <button className="mt-2 text-xs underline" onClick={load}>
                  Try again
                </button>
              </div>
            </div>
          ) : (
            settings && (
              <>
                {/* Model */}
                <Section
                  title="Language model"
                  description="Choose which locally installed Ollama model generates answers."
                >
                  <Field label="Model" hint="Only models installed in Ollama are listed.">
                    <select
                      className="input"
                      value={settings.model}
                      onChange={(e) => set("model", e.target.value)}
                    >
                      {currentMissing && <option value={settings.model}>{settings.model} (not installed)</option>}
                      {models.length === 0 && !currentMissing && <option value="">No models found</option>}
                      {models.map((m) => (
                        <option key={m.name} value={m.name}>
                          {m.name}
                          {m.size ? ` — ${formatBytes(m.size)}` : ""}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <Field label="Context window (tokens)" hint="Passed to Ollama as num_ctx.">
                      <input
                        type="number"
                        min={512}
                        max={131072}
                        step={512}
                        className="input"
                        value={settings.context_window}
                        onChange={(e) => set("context_window", Number(e.target.value))}
                      />
                    </Field>
                    <Field label="History limit (messages)" hint="Previous messages sent with each request.">
                      <input
                        type="number"
                        min={1}
                        max={100}
                        className="input"
                        value={settings.history_limit}
                        onChange={(e) => set("history_limit", Number(e.target.value))}
                      />
                    </Field>
                  </div>
                </Section>

                {/* STT */}
                <Section title="Speech-to-text" description="Local faster-whisper transcription.">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <Field label="Whisper model" hint="Larger models are more accurate but slower and need more RAM.">
                      <select
                        className="input"
                        value={settings.stt_model}
                        onChange={(e) => set("stt_model", e.target.value)}
                      >
                        {WHISPER_MODELS.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Language" hint='Use "auto" to detect automatically.'>
                      <input
                        className="input"
                        value={settings.stt_language}
                        onChange={(e) => set("stt_language", e.target.value.trim())}
                        placeholder="auto"
                      />
                    </Field>
                  </div>
                </Section>

                {/* TTS */}
                <Section title="Text-to-speech" description="Local Piper voice profiles.">
                  <Field label="Voice">
                    <div className="flex gap-2">
                      <select
                        className="input"
                        value={prefs.ttsVoice}
                        onChange={(e) => updatePrefs({ ttsVoice: e.target.value })}
                      >
                        <option value="">Default voice</option>
                        {voices.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name}
                            {v.language ? ` (${v.language})` : ""}
                          </option>
                        ))}
                      </select>
                      <button className="btn-outline flex-none" onClick={testVoice} disabled={testing}>
                        {testing ? <Loader2 size={14} className="animate-spin" /> : <Volume2 size={14} />} Test
                      </button>
                    </div>
                    {voices.length === 0 && (
                      <span className="mt-1 block text-[11px] text-amber-400">
                        No voices reported by the backend. Install a Piper voice (see the README).
                      </span>
                    )}
                  </Field>
                  <Toggle
                    label="Mute speech"
                    hint="Disables all spoken responses."
                    checked={prefs.ttsMuted}
                    onChange={(v) => updatePrefs({ ttsMuted: v })}
                  />
                </Section>

                {/* RAG */}
                <Section
                  title="Knowledge base (RAG)"
                  description="Chunk size and overlap apply to documents uploaded after saving."
                >
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <Field label="Chunk size">
                      <input
                        type="number"
                        min={100}
                        max={4000}
                        className="input"
                        value={settings.rag.chunk_size}
                        onChange={(e) => set("rag.chunk_size", Number(e.target.value))}
                      />
                    </Field>
                    <Field label="Overlap">
                      <input
                        type="number"
                        min={0}
                        max={1000}
                        className="input"
                        value={settings.rag.chunk_overlap}
                        onChange={(e) => set("rag.chunk_overlap", Number(e.target.value))}
                      />
                    </Field>
                    <Field label="Top-K results">
                      <input
                        type="number"
                        min={1}
                        max={20}
                        className="input"
                        value={settings.rag.top_k}
                        onChange={(e) => set("rag.top_k", Number(e.target.value))}
                      />
                    </Field>
                    <Field label="Min. relevance">
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.05}
                        className="input"
                        value={settings.rag.min_score}
                        onChange={(e) => set("rag.min_score", Number(e.target.value))}
                      />
                    </Field>
                  </div>
                  {settings.rag.chunk_overlap >= settings.rag.chunk_size && (
                    <p className="text-xs text-amber-400">Overlap must be smaller than the chunk size.</p>
                  )}
                </Section>

                {/* App */}
                <Section title="Application">
                  <Toggle
                    label="Use knowledge base in chat"
                    hint="Retrieve relevant document passages for every question."
                    checked={prefs.useKnowledgeBase}
                    onChange={(v) => updatePrefs({ useKnowledgeBase: v })}
                  />
                  <Toggle
                    label="Speak answers in voice mode"
                    hint="Read the response aloud after a spoken question."
                    checked={prefs.autoSpeak}
                    onChange={(v) => updatePrefs({ autoSpeak: v })}
                  />
                  <Toggle
                    label="Continuous conversation"
                    hint="In voice mode, start listening again after each spoken answer."
                    checked={prefs.continuousMode}
                    onChange={(v) => updatePrefs({ continuousMode: v })}
                  />
                </Section>

                {/* Save bar */}
                <div className="sticky bottom-0 -mx-4 flex items-center justify-between gap-3 border-t border-ink-700 bg-ink-950/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
                  <div className="min-w-0 text-xs">
                    {saveMsg ? (
                      <span
                        className={`flex items-center gap-1.5 ${
                          saveMsg.type === "success" ? "text-emerald-400" : "text-red-400"
                        }`}
                      >
                        {saveMsg.type === "success" ? <Check size={13} /> : <AlertCircle size={13} />}
                        {saveMsg.text}
                      </span>
                    ) : dirty ? (
                      <span className="text-zinc-400">You have unsaved changes.</span>
                    ) : (
                      <span className="text-zinc-600">All changes saved.</span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button className="btn-ghost" onClick={() => setSettings(initial)} disabled={!dirty || saving}>
                      Reset
                    </button>
                    <button
                      className="btn-primary"
                      onClick={save}
                      disabled={!dirty || saving || settings.rag.chunk_overlap >= settings.rag.chunk_size}
                    >
                      {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save
                    </button>
                  </div>
                </div>
              </>
            )
          )}
        </div>
      </div>
    </div>
  );
}
