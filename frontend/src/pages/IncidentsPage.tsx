import { useState, useEffect, useCallback } from "react";
import { T, TT } from "../lib/theme";

// ── Types ────────────────────────────────────────────────────────────────────

type IncidentSummary = {
  id:             string;
  triggered_at:   string;
  trigger_source: string;
  status:         "OPEN" | "RESOLVED" | "NOISE" | "ANALYZING";
  severity:       "HIGH" | "MED" | "LOW";
  failure_mode:   string;
  namespace:      string;
  affected_pods:  string[];
  root_cause:     string;
  confidence:     number;
  duration_s:     number;
};

type ActionItem = { action: string; priority: "P0" | "P1" | "P2"; owner: string };
type TimelineEvent = { time: string; event: string };

type IncidentDetail = IncidentSummary & {
  triage_output:   Record<string, unknown> | null;
  evidence_output: Record<string, unknown> | null;
  rca_output: {
    reasoning_steps:      string[];
    root_cause:           string;
    confidence:           number;
    contributing_factors: string[];
    ruled_out:            string[];
    severity:             string;
    affected_components:  string[];
  } | null;
  postmortem: {
    title:                string;
    impact:               string;
    timeline:             TimelineEvent[];
    root_cause:           string;
    contributing_factors: string[];
    what_went_well:       string[];
    action_items:         ActionItem[];
    lessons_learned:      string;
    blameless_statement:  string;
  } | null;
};

// ── Helpers ──────────────────────────────────────────────────────────────────

const SEV_CLASS: Record<string, string> = {
  HIGH: "badge-crit",
  MED:  "badge-warn",
  LOW:  "badge-muted",
};

const STATUS_CLASS: Record<string, string> = {
  OPEN:      "badge-crit",
  ANALYZING: "badge-info",
  RESOLVED:  "badge-ok",
  NOISE:     "badge-muted",
};

const PRI_CLASS: Record<string, string> = {
  P0: "text-crit font-semibold",
  P1: "text-warn",
  P2: "text-sec",
};

function fmtTime(iso: string) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function fmtDuration(s: number) {
  if (!s) return "—";
  if (s < 60)  return `${Math.round(s)}s`;
  return `${Math.round(s / 60)}m ${Math.round(s % 60)}s`;
}

function pct(n: number) {
  return `${Math.round((n ?? 0) * 100)}%`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SeverityBadge({ sev }: { sev: string }) {
  return <span className={`badge ${SEV_CLASS[sev] ?? "badge-muted"}`}>{sev}</span>;
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${STATUS_CLASS[status] ?? "badge-muted"}`}>
      {status === "ANALYZING" && <span className="dot dot-info blink mr-1" />}
      {status}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-bd rounded-sm">
      <div className="px-4 py-2 border-b border-bd bg-raised">
        <span className="text-[11px] font-semibold text-sec uppercase tracking-wide">{title}</span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function ReasoningStep({ step, idx }: { step: string; idx: number }) {
  return (
    <div className="flex gap-3 text-[12px]">
      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-raised border border-bd
                       flex items-center justify-center text-[10px] text-sec font-mono">
        {idx + 1}
      </span>
      <span className="text-sec leading-relaxed pt-0.5">{step}</span>
    </div>
  );
}

function PostmortemPanel({ pm }: { pm: NonNullable<IncidentDetail["postmortem"]> }) {
  return (
    <div className="space-y-4">
      <div>
        <div className="text-[11px] text-mut uppercase tracking-wide mb-1">Impact</div>
        <p className="text-[12px] text-sec leading-relaxed">{pm.impact}</p>
      </div>

      {pm.timeline?.length > 0 && (
        <div>
          <div className="text-[11px] text-mut uppercase tracking-wide mb-2">Timeline</div>
          <div className="space-y-1">
            {pm.timeline.map((e, i) => (
              <div key={i} className="flex gap-3 text-[12px]">
                <span className="font-mono text-acct w-20 flex-shrink-0">{e.time}</span>
                <span className="text-sec">{e.event}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {pm.contributing_factors?.length > 0 && (
        <div>
          <div className="text-[11px] text-mut uppercase tracking-wide mb-2">Contributing Factors</div>
          <ul className="space-y-1">
            {pm.contributing_factors.map((f, i) => (
              <li key={i} className="text-[12px] text-sec flex gap-2">
                <span className="text-warn">▸</span>{f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {pm.what_went_well?.length > 0 && (
        <div>
          <div className="text-[11px] text-mut uppercase tracking-wide mb-2">What Went Well</div>
          <ul className="space-y-1">
            {pm.what_went_well.map((f, i) => (
              <li key={i} className="text-[12px] text-sec flex gap-2">
                <span className="text-ok">▸</span>{f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {pm.action_items?.length > 0 && (
        <div>
          <div className="text-[11px] text-mut uppercase tracking-wide mb-2">Action Items</div>
          <div className="space-y-1">
            {pm.action_items.map((a, i) => (
              <div key={i} className="flex items-start gap-3 text-[12px]">
                <span className={`w-7 flex-shrink-0 ${PRI_CLASS[a.priority] ?? ""}`}>{a.priority}</span>
                <span className="text-pri flex-1">{a.action}</span>
                <span className="text-mut text-[10px]">{a.owner}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {pm.lessons_learned && (
        <div>
          <div className="text-[11px] text-mut uppercase tracking-wide mb-1">Lessons Learned</div>
          <p className="text-[12px] text-sec leading-relaxed">{pm.lessons_learned}</p>
        </div>
      )}

      {pm.blameless_statement && (
        <div className="p-3 bg-emerald-50 border border-ok rounded-sm">
          <p className="text-[11px] text-ok">{pm.blameless_statement}</p>
        </div>
      )}
    </div>
  );
}

function DetailPanel({
  incident,
  onClose,
  onResolve,
}: {
  incident: IncidentDetail;
  onClose: () => void;
  onResolve: (id: string) => void;
}) {
  const [tab, setTab] = useState<"rca" | "postmortem" | "raw">("rca");

  return (
    <div className="fixed inset-0 z-40 flex">
      {/* backdrop */}
      <div className="flex-1 bg-black/20" onClick={onClose} />

      {/* panel */}
      <div className="w-[640px] bg-surface border-l border-bd flex flex-col overflow-hidden shadow-xl">

        {/* header */}
        <div className="px-5 py-4 border-b border-bd flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-[11px] text-acct">{incident.id}</span>
              <SeverityBadge sev={incident.severity} />
              <StatusBadge status={incident.status} />
            </div>
            <h2 className="text-pri font-semibold text-sm mt-1 leading-snug line-clamp-2">
              {incident.postmortem?.title ?? incident.failure_mode ?? "Incident"}
            </h2>
            <div className="text-[11px] text-mut mt-0.5">
              {incident.namespace} · {fmtTime(incident.triggered_at)} · {fmtDuration(incident.duration_s)} pipeline
            </div>
          </div>
          <button onClick={onClose} className="text-mut hover:text-pri text-lg leading-none flex-shrink-0">✕</button>
        </div>

        {/* root cause bar */}
        <div className="px-5 py-3 border-b border-bd bg-raised">
          <div className="text-[10px] text-mut uppercase tracking-wide mb-1">
            Root Cause · Confidence {pct(incident.confidence)}
          </div>
          <p className="text-[12px] text-pri leading-snug">{incident.root_cause || "—"}</p>
          <div className="mt-2 h-1 bg-bd rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-acct"
              style={{ width: pct(incident.confidence) }}
            />
          </div>
        </div>

        {/* tabs */}
        <div className="flex border-b border-bd text-[11px]">
          {(["rca", "postmortem", "raw"] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2.5 font-medium uppercase tracking-wide transition-colors
                ${tab === t
                  ? "text-acct border-b-2 border-acct"
                  : "text-sec hover:text-pri"}`}
            >
              {t === "rca" ? "RCA" : t === "postmortem" ? "Postmortem" : "Raw Data"}
            </button>
          ))}
        </div>

        {/* tab content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">

          {tab === "rca" && incident.rca_output && (
            <>
              <Section title="Agent Reasoning">
                <div className="space-y-3">
                  {incident.rca_output.reasoning_steps?.map((s, i) => (
                    <ReasoningStep key={i} step={s} idx={i} />
                  ))}
                </div>
              </Section>

              {incident.rca_output.contributing_factors?.length > 0 && (
                <Section title="Contributing Factors">
                  <ul className="space-y-1">
                    {incident.rca_output.contributing_factors.map((f, i) => (
                      <li key={i} className="text-[12px] text-sec flex gap-2">
                        <span className="text-warn">▸</span>{f}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {incident.rca_output.ruled_out?.length > 0 && (
                <Section title="Ruled Out">
                  <ul className="space-y-1">
                    {incident.rca_output.ruled_out.map((f, i) => (
                      <li key={i} className="text-[12px] text-mut flex gap-2">
                        <span className="text-ok">✕</span>{f}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}
            </>
          )}

          {tab === "postmortem" && incident.postmortem && (
            <Section title={incident.postmortem.title}>
              <PostmortemPanel pm={incident.postmortem} />
            </Section>
          )}

          {tab === "postmortem" && !incident.postmortem && (
            <div className="text-center text-sec text-sm py-12">Postmortem not yet generated</div>
          )}

          {tab === "raw" && (
            <div className="space-y-3">
              {["triage_output", "evidence_output", "rca_output"].map(key => (
                <Section key={key} title={key.replace("_", " ").toUpperCase()}>
                  <pre className="text-[10px] font-mono text-sec overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify((incident as Record<string, unknown>)[key], null, 2)}
                  </pre>
                </Section>
              ))}
            </div>
          )}
        </div>

        {/* footer actions */}
        <div className="px-5 py-3 border-t border-bd flex items-center gap-3">
          {incident.status === "OPEN" && (
            <button
              onClick={() => onResolve(incident.id)}
              className="px-3 py-1.5 text-[11px] bg-emerald-50 border border-ok text-ok
                         hover:bg-emerald-100 rounded-sm transition-colors"
            >
              Mark Resolved
            </button>
          )}
          <button
            onClick={() => {
              const blob = new Blob([JSON.stringify(incident.postmortem, null, 2)],
                { type: "application/json" });
              const a = document.createElement("a");
              a.href = URL.createObjectURL(blob);
              a.download = `${incident.id}-postmortem.json`;
              a.click();
            }}
            className="px-3 py-1.5 text-[11px] bg-raised border border-bd text-sec
                       hover:text-pri rounded-sm transition-colors"
          >
            Export Postmortem
          </button>
          <span className="flex-1" />
          <span className="text-[10px] text-mut font-mono">
            Pipeline: {fmtDuration(incident.duration_s)}
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function IncidentsPage() {
  const [incidents, setIncidents]   = useState<IncidentSummary[]>([]);
  const [detail,    setDetail]      = useState<IncidentDetail | null>(null);
  const [loading,   setLoading]     = useState(true);
  const [filter,    setFilter]      = useState<"ALL" | "OPEN" | "RESOLVED">("ALL");

  const fetchList = useCallback(async () => {
    try {
      const params = filter !== "ALL" ? `?status=${filter}` : "";
      const r = await fetch(`/api/incidents${params}`);
      const data = await r.json();
      setIncidents(Array.isArray(data) ? data : []);
    } catch {
      setIncidents([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { fetchList(); }, [fetchList]);

  // Auto-refresh every 10s for live updates
  useEffect(() => {
    const id = setInterval(fetchList, 10_000);
    return () => clearInterval(id);
  }, [fetchList]);

  const openDetail = async (id: string) => {
    try {
      const r = await fetch(`/api/incidents/${id}`);
      setDetail(await r.json());
    } catch { /* ignore */ }
  };

  const handleResolve = async (id: string) => {
    await fetch(`/api/incidents/${id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "RESOLVED" }),
    });
    setDetail(null);
    fetchList();
  };

  const openCount = incidents.filter(i => i.status === "OPEN").length;

  return (
    <div className="p-5 space-y-4">

      {/* header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-pri">Incident Diagnosis</h1>
          <p className="text-[11px] text-mut mt-0.5">
            Automated root cause analysis · LangChain 4-agent pipeline · Ollama llama3.1:8b
          </p>
        </div>
        <div className="flex items-center gap-2">
          {openCount > 0 && (
            <span className="badge badge-crit">{openCount} OPEN</span>
          )}
          {(["ALL", "OPEN", "RESOLVED"] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 text-[11px] border rounded-sm transition-colors
                ${filter === f
                  ? "bg-acct text-white border-acct"
                  : "bg-raised border-bd text-sec hover:text-pri"}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* table */}
      <div className="card">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-sec text-sm">Loading incidents…</div>
          ) : incidents.length === 0 ? (
            <div className="p-8 text-center text-sec text-sm">
              No incidents yet. Trigger a diagnosis from the
              <button className="text-acct mx-1 hover:underline" onClick={() => {}}>
                Live Diagnosis
              </button>
              page or wait for Alertmanager to fire.
            </div>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Severity</th>
                  <th>Failure</th>
                  <th>Namespace</th>
                  <th>Root Cause</th>
                  <th>Confidence</th>
                  <th>Time</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map(inc => (
                  <tr
                    key={inc.id}
                    className="cursor-pointer hover:bg-hover transition-colors"
                    onClick={() => openDetail(inc.id)}
                  >
                    <td className="font-mono text-acct text-[10px]">{inc.id}</td>
                    <td><SeverityBadge sev={inc.severity} /></td>
                    <td className="font-mono text-[11px] text-sec">{inc.failure_mode || "—"}</td>
                    <td className="text-sec">{inc.namespace || "—"}</td>
                    <td className="max-w-[240px] truncate text-[11px]" title={inc.root_cause}>
                      {inc.root_cause || "—"}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-bd rounded-full overflow-hidden">
                          <div
                            className="h-full bg-acct rounded-full"
                            style={{ width: pct(inc.confidence) }}
                          />
                        </div>
                        <span className="text-[10px] text-mut font-mono">{pct(inc.confidence)}</span>
                      </div>
                    </td>
                    <td className="text-[10px] text-mut whitespace-nowrap">{fmtTime(inc.triggered_at)}</td>
                    <td><StatusBadge status={inc.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* detail panel */}
      {detail && (
        <DetailPanel
          incident={detail}
          onClose={() => setDetail(null)}
          onResolve={handleResolve}
        />
      )}
    </div>
  );
}
