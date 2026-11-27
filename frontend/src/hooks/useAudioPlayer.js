import { useCallback, useEffect, useRef, useState } from "react";
import { voiceApi, getErrorMessage } from "../services/api.js";
import { markdownToPlainText } from "../utils/format.js";
import { useApp } from "../context/AppContext.jsx";

/**
 * Text-to-speech playback. One clip at a time.
 * speak() resolves when playback finishes (or is stopped), which lets the
 * voice-conversation flow wait for the answer to be heard.
 */
export function useAudioPlayer() {
  const { prefs } = useApp();
  const [activeId, setActiveId] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | loading | playing | paused
  const [error, setError] = useState("");

  const audioRef = useRef(null);
  const urlRef = useRef(null);
  const cacheRef = useRef(new Map()); // `${id}|${voice}` -> Blob
  const finishRef = useRef(null);
  const tokenRef = useRef(0); // invalidates stale async work after stop()

  const release = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }, []);

  const settle = useCallback(() => {
    const fn = finishRef.current;
    finishRef.current = null;
    fn?.();
  }, []);

  const stop = useCallback(() => {
    tokenRef.current++;
    release();
    setActiveId(null);
    setStatus("idle");
    settle();
  }, [release, settle]);

  const speak = useCallback(
    async (id, text, { force = false } = {}) => {
      if (prefs.ttsMuted) return;
      const plain = markdownToPlainText(text);
      if (!plain) return;

      stop();
      const token = ++tokenRef.current;
      setError("");
      setActiveId(id);
      setStatus("loading");

      try {
        const key = `${id}|${prefs.ttsVoice}`;
        let blob = force ? null : cacheRef.current.get(key);
        if (!blob) {
          blob = await voiceApi.speak(plain, prefs.ttsVoice || undefined);
          if (token !== tokenRef.current) return; // stopped while generating
          cacheRef.current.set(key, blob);
        }

        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        const audio = new Audio(url);
        audioRef.current = audio;

        await new Promise((resolve) => {
          finishRef.current = resolve;
          audio.onended = () => {
            if (token !== tokenRef.current) return;
            release();
            setActiveId(null);
            setStatus("idle");
            settle();
          };
          audio.onerror = () => {
            if (token !== tokenRef.current) return;
            setError("Audio playback failed.");
            release();
            setActiveId(null);
            setStatus("idle");
            settle();
          };
          audio
            .play()
            .then(() => token === tokenRef.current && setStatus("playing"))
            .catch((e) => {
              if (token !== tokenRef.current) return;
              setError(
                e?.name === "NotAllowedError"
                  ? "Your browser blocked autoplay. Click the speaker icon to play."
                  : "Audio playback failed."
              );
              release();
              setActiveId(null);
              setStatus("idle");
              settle();
            });
        });
      } catch (err) {
        if (token !== tokenRef.current) return;
        setError(getErrorMessage(err, "Could not generate speech"));
        release();
        setActiveId(null);
        setStatus("idle");
      }
    },
    [prefs.ttsMuted, prefs.ttsVoice, release, settle, stop]
  );

  const pause = useCallback(() => {
    if (audioRef.current && status === "playing") {
      audioRef.current.pause();
      setStatus("paused");
    }
  }, [status]);

  const resume = useCallback(() => {
    if (audioRef.current && status === "paused") {
      audioRef.current.play();
      setStatus("playing");
    }
  }, [status]);

  // Muting should silence anything currently playing.
  useEffect(() => {
    if (prefs.ttsMuted) stop();
  }, [prefs.ttsMuted, stop]);

  useEffect(() => stop, [stop]);

  return { activeId, status, error, setError, speak, pause, resume, stop };
}
