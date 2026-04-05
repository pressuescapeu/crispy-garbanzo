import { useEffect, useRef, useState } from "react";
import type { LogEntry } from "../types";
import { sendToBackend, getCursorPosition } from "../agentSocket";

type SpeechRecognitionLike = EventTarget & {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

type SpeechRecognitionErrorEventLike = {
  error: string;
};

type SpeechRecognitionResultLike = {
  isFinal: boolean;
  0?: { transcript: string };
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
};

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

// Flush after this many ms of silence (no new final speech result)
const SILENCE_MS = 4_500;

function nowTimeString() {
  return new Date().toISOString();
}

export function useSpeechRecorder(username: string = 'unknown') {
  const [isRecording, setIsRecording] = useState(false);
  const [chunkCount, setChunkCount] = useState(0);
  const [interimText, setInterimText] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const silenceTimerRef = useRef<number | null>(null);
  const finalBufferRef = useRef("");
  const chunkRef = useRef(0);
  const isRecordingRef = useRef(false);
  const logIdRef = useRef(1);

  const addLog = (message: string, type: LogEntry["type"]) => {
    const entry: LogEntry = {
      id: logIdRef.current++,
      timestamp: nowTimeString(),
      message,
      type,
    };
    setLogs((prev) => [...prev, entry]);
  };

  const flushChunk = async () => {
    chunkRef.current += 1;
    const currentChunk = chunkRef.current;
    setChunkCount(currentChunk);

    const text = finalBufferRef.current.trim();
    finalBufferRef.current = "";
    setInterimText("");

    if (!text) {
      addLog(`chunk ${currentChunk} - silence, skipped`, "warn");
      return;
    }

    try {
      const response = await fetch("/api/transcript", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          chunk: currentChunk,
          text,
        }),
      });

      if (!response.ok) {
        const errorBody = await response.text().catch(() => "");
        throw new Error(`HTTP ${response.status} ${errorBody}`.trim());
      }

      addLog(`chunk ${currentChunk} saved (${text.slice(0, 60)})`, "success");

      const cursor = getCursorPosition()
      sendToBackend({
        event: "transcript_chunk",
        chunk: currentChunk,
        text,
        user: username,
        timestamp: new Date().toISOString(),
        cursorX: cursor.x,
        cursorY: cursor.y,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      addLog(`chunk ${currentChunk} failed: ${message}`, "error");
    }
  };

  // Called each time a final speech result arrives — resets the silence countdown
  const armSilenceTimer = () => {
    if (silenceTimerRef.current !== null) {
      window.clearTimeout(silenceTimerRef.current);
    }
    silenceTimerRef.current = window.setTimeout(() => {
      void flushChunk();
    }, SILENCE_MS);
  };

  const clearSilenceTimer = () => {
    if (silenceTimerRef.current !== null) {
      window.clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  const stopRecognition = () => {
    const recognition = recognitionRef.current;
    if (!recognition) return;

    recognition.onend = null;
    recognition.onresult = null;
    recognition.onerror = null;
    recognition.stop();
    recognitionRef.current = null;
  };

  const stopRecording = async () => {
    if (!isRecordingRef.current) return;

    isRecordingRef.current = false;
    setIsRecording(false);
    clearSilenceTimer();
    stopRecognition();

    if (finalBufferRef.current.trim()) {
      await flushChunk();
    }

    setInterimText("");
    addLog("recording stopped", "info");
  };

  const startRecording = () => {
    setError(null);

    const RecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!RecognitionCtor) {
      const notSupported = "Web Speech API is not supported in this browser. Use Chrome or Edge.";
      setError(notSupported);
      addLog(notSupported, "error");
      return;
    }

    if (isRecordingRef.current) return;

    finalBufferRef.current = "";
    chunkRef.current = 0;
    setChunkCount(0);
    setInterimText("");

    const recognition = new RecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const transcript = result?.[0]?.transcript?.trim() ?? "";
        if (!transcript) continue;

        if (result.isFinal) {
          finalBufferRef.current += `${transcript} `;
          // Each final result resets the silence countdown
          armSilenceTimer();
        } else {
          interim += `${transcript} `;
        }
      }
      setInterimText(interim.trim());
    };

    recognition.onerror = (event: SpeechRecognitionErrorEventLike) => {
      const message = `SpeechRecognition error: ${event.error}`;
      setError(message);
      addLog(message, "error");
    };

    recognition.onend = () => {
      if (!isRecordingRef.current) return;
      try {
        recognition.start();
        addLog("recognition restarted", "info");
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        addLog(`restart failed: ${message}`, "error");
      }
    };

    try {
      recognition.start();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      addLog(`failed to start recognition: ${message}`, "error");
      return;
    }

    recognitionRef.current = recognition;
    isRecordingRef.current = true;
    setIsRecording(true);

    addLog("recording started", "info");
  };

  useEffect(() => {
    return () => {
      void stopRecording();
    };
  }, []);

  return {
    isRecording,
    chunkCount,
    interimText,
    logs,
    error,
    startRecording,
    stopRecording,
  };
}
