import { useEffect, useRef, useState } from "react";

type LogLine = { ts: string; stream: string; text: string; level: string };

function levelOf(line: string): string {
  const l = line.toLowerCase();
  if (l.includes("error") || l.includes("err")) return "error";
  if (l.includes("warn"))  return "warn";
  if (l.includes("debug")) return "debug";
  return "info";
}

const LEVEL_STYLE: Record<string, string> = {
  error: "text-crit",
  warn:  "text-warn",
  info:  "text-pri",
  debug: "text-sec",
};

export default function LogPanel() {
  const [logs,  setLogs]  = useState<LogLine[]>([]);
  const [query, setQuery] = useState('{namespace="monitoring"}');
  const [err,   setErr]   = useState(false);
  const bottomRef  = useRef<HTMLDivElement>(null);
  const autoScroll = useRef(true);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch(`/api/loki?query=${encodeURIComponent(query)}&limit=30&since=2m`);
        const data = await r.json();
        const streams = data?.data?.result ?? [];
        const lines: LogLine[] = [];
        for (const s of streams) {
          const stream = Object.values(s.stream as Record<string, string>).join("/");
          for (const [ts, text] of s.values ?? []) {
            lines.push({ ts: new Date(parseInt(ts) / 1e6).toISOString().slice(11, 19), stream, text, level: levelOf(text) });
          }
        }
        lines.sort((a, b) => a.ts.localeCompare(b.ts));
        setLogs(prev => [...prev, ...lines].slice(-200));
        setErr(false);
      } catch { setErr(true); }
    };
    load();
    const iv = setInterval(load, 5_000);
    return () => clearInterval(iv);
  }, [query]);

  useEffect(() => {
    if (autoScroll.current) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="card flex flex-col h-full min-h-0">
      <div className="card-header">
        <span className="card-title">Log Stream · Loki</span>
        {err && <span className="badge badge-crit">Error</span>}
      </div>
      <div className="p-2 border-b border-bdl flex gap-2">
        <input className="ent-input flex-1 text-xs" value={query} onChange={e => setQuery(e.target.value)} spellCheck={false} />
      </div>
      <div
        className="flex-1 overflow-y-auto font-mono text-[11px] min-h-0"
        onScroll={e => {
          const el = e.currentTarget;
          autoScroll.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
      >
        {logs.length === 0 && <div className="p-4 text-sec text-center">{err ? "Loki unreachable" : "Waiting for logs…"}</div>}
        {logs.map((l, i) => (
          <div key={i} className={`flex gap-2 px-3 py-0.5 border-b border-bdl hover:bg-raised ${LEVEL_STYLE[l.level]}`}>
            <span className="text-sec flex-shrink-0 w-20">{l.ts}</span>
            <span className="text-mut flex-shrink-0 truncate w-24 hidden md:block">{l.stream}</span>
            <span className="truncate">{l.text}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
