import { useEffect, useRef, useState } from "react";

type LogLine = { ts: string; ns: string; level: string; text: string };

const LEVEL_STYLE: Record<string, string> = {
  error: "text-crit",
  warn:  "text-warn",
  info:  "text-pri",
  debug: "text-sec",
};

const LEVEL_BADGE: Record<string, string> = {
  error: "badge-crit",
  warn:  "badge-warn",
  info:  "badge-muted",
  debug: "badge-muted",
};

function levelOf(text: string): string {
  const l = text.toLowerCase();
  if (l.includes("error") || l.includes("err") || l.includes("fatal")) return "error";
  if (l.includes("warn"))  return "warn";
  if (l.includes("debug")) return "debug";
  return "info";
}

export default function LogsPage() {
  const [logs,  setLogs]  = useState<LogLine[]>([]);
  const [query, setQuery] = useState('{namespace="monitoring"}');
  const [age,   setAge]   = useState(0);
  const [err,   setErr]   = useState(false);
  const [level, setLevel] = useState<string>("all");
  const bottomRef  = useRef<HTMLDivElement>(null);
  const autoScroll = useRef(true);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch(`/api/loki?query=${encodeURIComponent(query)}&limit=50&since=5m`);
        const data = await r.json();
        const streams = data?.data?.result ?? [];
        const lines: LogLine[] = [];
        for (const s of streams) {
          const ns = (s.stream as Record<string, string>)["namespace"] || Object.values(s.stream as Record<string, string>).join("/");
          for (const [ts, text] of s.values ?? []) {
            lines.push({
              ts:    new Date(parseInt(ts) / 1e6).toISOString().slice(11, 23),
              ns,
              level: levelOf(text),
              text,
            });
          }
        }
        lines.sort((a, b) => a.ts.localeCompare(b.ts));
        setLogs(prev => [...prev, ...lines].slice(-500));
        setAge(0);
        setErr(false);
      } catch {
        setErr(true);
      }
    };
    load();
    const iv = setInterval(load, 5_000);
    return () => clearInterval(iv);
  }, [query]);

  useEffect(() => {
    const iv = setInterval(() => setAge(a => a + 1), 1000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (autoScroll.current) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const filtered = level === "all" ? logs : logs.filter(l => l.level === level);

  return (
    <div className="p-5 h-full flex flex-col gap-3" style={{ minHeight: 0 }}>

      {/* ── Controls ─────────────────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="card-title">Log Stream · Loki</span>
            {err && <span className="badge badge-crit">Connection Error</span>}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {["all","error","warn","info","debug"].map(l => (
              <button
                key={l}
                onClick={() => setLevel(l)}
                className={`px-2.5 py-1 text-[10px] rounded-sm border transition-colors uppercase font-semibold ${
                  level === l ? "bg-acct border-acct text-pri" : "bg-raised border-bd text-sec hover:text-pri"
                }`}
              >
                {l}
              </button>
            ))}
            <span className="text-[11px] text-mut font-mono">T+{age}s</span>
          </div>
        </div>
        <div className="p-3 flex items-center gap-2">
          <span className="text-sec text-xs">Query</span>
          <input
            className="ent-input flex-1 text-xs"
            value={query}
            onChange={e => setQuery(e.target.value)}
            spellCheck={false}
          />
        </div>
      </div>

      {/* ── Log output ───────────────────────────────────────── */}
      <div
        className="card flex-1 overflow-y-auto text-[11px] font-mono"
        style={{ minHeight: 0 }}
        onScroll={e => {
          const el = e.currentTarget;
          autoScroll.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
        }}
      >
        {filtered.length === 0 && (
          <div className="p-6 text-center text-sec">
            {err ? "Failed to connect to Loki" : "Waiting for logs…"}
          </div>
        )}
        {filtered.map((l, i) => (
          <div
            key={i}
            className={`flex gap-3 px-3 py-1 border-b border-bdl hover:bg-raised transition-colors ${LEVEL_STYLE[l.level]}`}
          >
            <span className="text-mut flex-shrink-0 w-28">{l.ts}</span>
            <span className="flex-shrink-0">
              <span className={`badge ${LEVEL_BADGE[l.level]} text-[9px]`}>{l.level.toUpperCase()}</span>
            </span>
            <span className="text-sec flex-shrink-0 w-28 truncate hidden md:block">{l.ns}</span>
            <span className="truncate">{l.text}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="text-[11px] text-sec flex justify-between px-1">
        <span>{filtered.length} lines displayed</span>
        <span className="font-mono">Auto-scroll: {autoScroll.current ? "on" : "off"}</span>
      </div>
    </div>
  );
}
