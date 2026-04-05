import { useEffect, useMemo, useRef } from "react";
import type { LogEntry } from "../types";

type LiveLogProps = {
  logs: LogEntry[];
  interimText: string;
};

function toClock(iso: string) {
  const date = new Date(iso);
  return date.toLocaleTimeString("en-US", { hour12: false });
}

export function LiveLog({ logs, interimText }: LiveLogProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, interimText]);

  const rendered = useMemo(() => {
    return logs.map((log) => (
      <div key={log.id} className="log-row">
        <span className="log-time">[{toClock(log.timestamp)}]</span>
        <span className={`log-msg ${log.type}`}>{log.message}</span>
      </div>
    ));
  }, [logs]);

  return (
    <div className="log-panel" ref={containerRef}>
      {rendered.length ? rendered : <div className="log-empty">No logs yet.</div>}
      {interimText ? (
        <div className="log-row live-line">
          <span className="live-dot">●</span>
          <span className="log-msg info">{interimText}</span>
        </div>
      ) : null}
    </div>
  );
}
