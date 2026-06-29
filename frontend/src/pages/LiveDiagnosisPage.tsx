import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ScanSearch, FileSearch2, Brain, FileText,
  CheckCircle2, Loader2, XCircle, Play, RotateCcw,
  Sparkles, ArrowRight, ShieldAlert, type LucideIcon,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────

type StepStatus = "waiting" | "running" | "done" | "error";

type AgentStep = {
  agent:   "triage" | "evidence" | "rca" | "postmortem" | "pipeline";
  status:  StepStatus;
  output?: Record<string, unknown>;
  started_at?: number;
  done_at?:    number;
};

type DiagState = "idle" | "running" | "complete" | "error";

// ── Agent metadata ───────────────────────────────────────────────────────────

const AGENT_META: Record<string, { label: string; short: string; desc: string; icon: LucideIcon }> = {
  triage:     { label: "Triage Agent",     short: "Triage",     icon: ScanSearch,  desc: "Identifies affected pods and failure mode via the Kubernetes API" },
  evidence:   { label: "Evidence Agent",   short: "Evidence",   icon: FileSearch2, desc: "Collects logs from Loki, metrics from Prometheus, and K8s events" },
  rca:        { label: "RCA Agent",        short: "Root Cause", icon: Brain,       desc: "Reasons over the evidence to identify the root cause" },
  postmortem: { label: "Postmortem Agent", short: "Postmortem", icon: FileText,    desc: "Generates a blameless postmortem with action items" },
};

const AGENT_ORDER = ["triage", "evidence", "rca", "postmortem"];

const STYLE: Record<StepStatus, { icon: string; ring: string; bg: string; line: string }> = {
  waiting: { icon: "text-mut",  ring: "border-bd",      bg: "bg-raised",     line: "bg-bd" },
  running: { icon: "text-acct", ring: "border-acct",    bg: "bg-blue-50",    line: "bg-bd" },
  done:    { icon: "text-ok",   ring: "border-ok/50",   bg: "bg-emerald-50", line: "bg-ok" },
  error:   { icon: "text-crit", ring: "border-crit",    bg: "bg-red-50",     line: "bg-bd" },
};

function elapsed(step: AgentStep): string {
  if (!step.started_at) return "";
  const end = step.done_at ?? Date.now();
  return `${Math.round((end - step.started_at) / 1000)}s`;
}

// ── Timeline node (icon + connector) ─────────────────────────────────────────

function NodeRail({ status, Icon, isLast }: { status: StepStatus; Icon: LucideIcon; isLast: boolean }) {
  const st = STYLE[status];
  return (
    <div className="flex flex-col items-center self-stretch">
      <div className={`relative w-10 h-10 rounded-full border flex items-center justify-center ${st.ring} ${st.bg}`}>
        {status === "running" && (
          <span className="absolute inset-0 rounded-full border-2 border-acct/30 animate-ping" />
        )}
        {status === "running"
          ? <Loader2 size={17} className="text-acct animate-spin" />
          : status === "error"
          ? <XCircle size={17} className="text-crit" />
          : <Icon size={17} className={st.icon} />}
        {status === "done" && (
          <span className="absolute -bottom-1 -right-1 bg-surface rounded-full">
            <CheckCircle2 size={14} className="text-ok" />
          </span>
        )}
      </div>
      {!isLast && <div className={`w-0.5 flex-1 min-h-[14px] my-1 rounded ${st.line} transition-colors duration-500`} />}
    </div>
  );
}

// ── One agent step on the timeline ───────────────────────────────────────────

function TimelineStep({ step, index, isLast }: { step: AgentStep; index: number; isLast: boolean }) {
  const meta = AGENT_META[step.agent] ?? { label: step.agent, short: step.agent, desc: "", icon: Sparkles };
  const active = step.status === "running";

  return (
    <div className="flex gap-3.5">
      <NodeRail status={step.status} Icon={meta.icon} isLast={isLast} />

      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, delay: index * 0.04 }}
        className={`flex-1 mb-3 rounded-md border bg-surface transition-all ${
          active ? "border-acct shadow-[0_0_0_3px_rgba(26,86,219,0.08)]" : "border-bd"
        }`}
      >
        <div className="flex items-center justify-between gap-3 px-3.5 py-2.5">
          <div className="min-w-0">
            <div className="text-[12px] font-semibold text-pri leading-tight">{meta.label}</div>
            <div className="text-[10.5px] text-mut truncate">{meta.desc}</div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {active && <span className="text-[10px] text-acct font-mono animate-pulse">analyzing…</span>}
            {(step.status === "done" || step.status === "error") && step.started_at && (
              <span className="text-[10px] text-mut font-mono">{elapsed(step)}</span>
            )}
            <span className={`badge text-[9px] ${
              step.status === "done"    ? "badge-ok"  :
              step.status === "running" ? "badge-info" :
              step.status === "error"   ? "badge-crit" : "badge-muted"
            }`}>{step.status.toUpperCase()}</span>
          </div>
        </div>

        <AnimatePresence>
          {step.status === "done" && step.output && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="px-3.5 pb-3 pt-2.5 border-t border-bd/60">
                <StepSummary agent={step.agent} output={step.output} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

// ── Per-agent output summaries ───────────────────────────────────────────────

function StepSummary({ agent, output }: { agent: string; output: Record<string, unknown> }) {
  const s = (v: unknown) => String(v ?? "—");
  const arr = (v: unknown) => Array.isArray(v) ? v as unknown[] : [];

  if (agent === "triage") {
    const sev = s(output.severity);
    return (
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px]">
        <div><span className="text-mut">Pods: </span><span className="font-mono text-pri">{arr(output.affected_pods).join(", ") || "—"}</span></div>
        <div><span className="text-mut">Mode: </span><span className="font-mono text-warn">{s(output.failure_mode)}</span></div>
        <div><span className="text-mut">Namespace: </span><span className="text-pri">{s(output.affected_namespace)}</span></div>
        <div><span className="text-mut">Severity: </span><span className={sev === "HIGH" ? "text-crit font-semibold" : "text-warn"}>{sev}</span></div>
        {!!output.summary && <div className="col-span-2 text-sec italic">"{s(output.summary)}"</div>}
      </div>
    );
  }

  if (agent === "evidence") {
    const recent = Boolean(output.recent_deployment);
    return (
      <div className="space-y-1.5 text-[11px]">
        {!!output.log_summary     && <div><span className="text-mut">Logs: </span><span className="text-sec">{s(output.log_summary)}</span></div>}
        {!!output.metric_findings && <div><span className="text-mut">Metrics: </span><span className="text-sec">{s(output.metric_findings)}</span></div>}
        {output.recent_deployment !== undefined && (
          <div><span className="text-mut">Recent deploy: </span>
            <span className={recent ? "text-warn" : "text-ok"}>{recent ? "YES — potential cause" : "No"}</span>
          </div>
        )}
      </div>
    );
  }

  if (agent === "rca") {
    const conf = typeof output.confidence === "number" ? Math.round(output.confidence * 100) : null;
    const sev  = s(output.severity);
    return (
      <div className="space-y-2 text-[11px]">
        <ol className="space-y-1.5">
          {arr(output.reasoning_steps).map((st, i) => (
            <li key={i} className="flex gap-2 text-sec">
              <span className="text-acct font-mono w-4 flex-shrink-0">{i + 1}.</span>
              <span>{s(st)}</span>
            </li>
          ))}
        </ol>
        {!!output.root_cause && (
          <div className="pt-2 mt-1 border-t border-bd/60 bg-blue-50/40 -mx-1 px-2 py-1.5 rounded">
            <span className="text-mut">Root cause: </span><span className="text-pri font-medium">{s(output.root_cause)}</span>
          </div>
        )}
        <div className="flex gap-5 pt-0.5">
          {conf !== null && (
            <div className="flex items-center gap-1.5">
              <span className="text-mut">Confidence</span>
              <div className="w-16 h-1.5 rounded-full bg-bd overflow-hidden">
                <div className="h-full bg-acct rounded-full" style={{ width: `${conf}%` }} />
              </div>
              <span className="text-acct font-semibold font-mono">{conf}%</span>
            </div>
          )}
          {!!output.severity && (
            <div><span className="text-mut">Severity: </span>
              <span className={sev === "HIGH" ? "text-crit font-semibold" : "text-warn"}>{sev}</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (agent === "postmortem") {
    type ActionItem = { action: string; priority: string };
    const items = arr(output.action_items) as ActionItem[];
    return (
      <div className="space-y-2 text-[11px]">
        {!!output.title && <div className="text-pri font-medium">"{s(output.title)}"</div>}
        {items.length > 0 && (
          <div className="space-y-1">
            <div className="text-[9px] uppercase tracking-wide text-mut">Action items</div>
            {items.map((a, i) => (
              <div key={i} className="flex gap-2 text-sec items-baseline">
                <span className={`badge text-[8px] ${a.priority === "P0" ? "badge-crit" : a.priority === "P1" ? "badge-warn" : "badge-muted"}`}>{a.priority}</span>
                <span>{a.action}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return null;
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function LiveDiagnosisPage({
  onIncidentCreated,
}: {
  onIncidentCreated?: (id: string) => void;
}) {
  const [namespace,  setNamespace]  = useState("");
  const [podName,    setPodName]    = useState("");
  const [state,      setState]      = useState<DiagState>("idle");
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [steps,      setSteps]      = useState<Record<string, AgentStep>>({});
  const [error,      setError]      = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const initSteps = (): Record<string, AgentStep> =>
    Object.fromEntries(AGENT_ORDER.map(a => [a, { agent: a as AgentStep["agent"], status: "waiting" }]));

  const handleStart = async () => {
    setError(null);
    setState("running");
    setSteps(initSteps());
    setIncidentId(null);

    try {
      const r = await fetch("/api/aiops/analyze", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ namespace, pod_name: podName, trigger_source: "manual" }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    } catch (e) {
      setError(String(e));
      setState("error");
      return;
    }

    const wsScheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${wsScheme}//${window.location.host}/ws/aiops/__all__`);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type !== "aiops_step") return;
        const { step, status, data } = msg;

        if (step === "pipeline" && status === "started") {
          const id = data?.incident_id;
          if (id) {
            setIncidentId(id);
            onIncidentCreated?.(id);
            ws.close();
            const ws2 = new WebSocket(`${wsScheme}//${window.location.host}/ws/aiops/${id}`);
            wsRef.current = ws2;
            ws2.onmessage = ws.onmessage;
          }
          return;
        }
        if (step === "pipeline" && (status === "complete" || status === "noise")) {
          setState("complete");
          return;
        }
        if (!AGENT_ORDER.includes(step)) return;

        setSteps(prev => ({
          ...prev,
          [step]: {
            agent:      step,
            status:     status === "running" ? "running" : status === "done" ? "done" : "waiting",
            output:     status === "done" ? data : undefined,
            started_at: status === "running" ? Date.now() : prev[step]?.started_at,
            done_at:    status === "done"    ? Date.now() : prev[step]?.done_at,
          },
        }));
      } catch { /* ignore parse errors */ }
    };

    ws.onerror = () => { setError("WebSocket connection failed"); setState("error"); };
  };

  const handleReset = () => {
    wsRef.current?.close();
    setState("idle");
    setSteps({});
    setIncidentId(null);
    setError(null);
  };

  useEffect(() => () => { wsRef.current?.close(); }, []);

  const doneCount  = AGENT_ORDER.filter(a => steps[a]?.status === "done").length;
  const allDone    = doneCount === AGENT_ORDER.length;
  const activeStep = AGENT_ORDER.find(a => steps[a]?.status === "running");
  const pct        = Math.round((doneCount / AGENT_ORDER.length) * 100);
  const running    = state === "running" || state === "complete";

  return (
    <div className="p-5 max-w-3xl mx-auto space-y-4">

      {/* header */}
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-md bg-acct/10 border border-acct/20 flex items-center justify-center flex-shrink-0">
          <ShieldAlert size={18} className="text-acct" />
        </div>
        <div>
          <h1 className="text-[15px] font-semibold text-pri leading-tight">Live Diagnosis</h1>
          <p className="text-[11px] text-mut mt-0.5">
            Run the 4-agent AIOps pipeline and watch each agent reason in real time
          </p>
        </div>
      </div>

      {/* trigger bar */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[150px]">
            <label className="block text-[10px] text-mut uppercase tracking-wide mb-1">Namespace (optional)</label>
            <input className="ent-input w-full" placeholder="e.g. netguard" value={namespace}
                   onChange={e => setNamespace(e.target.value)} disabled={state === "running"} />
          </div>
          <div className="flex-1 min-w-[150px]">
            <label className="block text-[10px] text-mut uppercase tracking-wide mb-1">Pod name hint (optional)</label>
            <input className="ent-input w-full" placeholder="e.g. inference-7d9c8b" value={podName}
                   onChange={e => setPodName(e.target.value)} disabled={state === "running"} />
          </div>
          {state === "idle" || state === "error" ? (
            <button onClick={handleStart}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-[11px] font-semibold bg-acct text-white hover:bg-blue-700 rounded-md transition-colors">
              <Play size={13} /> Run Diagnosis
            </button>
          ) : (
            <button onClick={handleReset} disabled={state === "running"}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-[11px] font-medium bg-raised border border-bd text-sec hover:text-pri rounded-md transition-colors disabled:opacity-40">
              <RotateCcw size={13} /> Reset
            </button>
          )}
        </div>
        {state === "idle" && (
          <p className="text-[11px] text-mut mt-3">Leave both fields empty to scan all namespaces for unhealthy pods.</p>
        )}
      </div>

      {/* live progress header */}
      {running && (
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center gap-2">
              {state === "complete"
                ? <CheckCircle2 size={15} className="text-ok" />
                : <Loader2 size={15} className="text-acct animate-spin" />}
              <span className="text-[12px] font-semibold text-pri">
                {state === "complete" ? "Diagnosis complete" : `Running — ${AGENT_META[activeStep ?? ""]?.label ?? "starting…"}`}
              </span>
              <span className="text-[10px] text-mut font-mono">({doneCount}/{AGENT_ORDER.length})</span>
            </div>
            {incidentId && <span className="font-mono text-[10px] text-acct">{incidentId}</span>}
          </div>
          <div className="progress-track">
            <div className={`progress-fill ${state === "complete" ? "bg-ok" : "bg-acct"}`} style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      {/* agent timeline */}
      {running && (
        <div className="pl-1">
          {AGENT_ORDER.map((a, i) => (
            <TimelineStep
              key={a}
              step={steps[a] ?? { agent: a as AgentStep["agent"], status: "waiting" }}
              index={i}
              isLast={i === AGENT_ORDER.length - 1}
            />
          ))}
        </div>
      )}

      {/* completion banner */}
      {state === "complete" && allDone && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="card p-4 border-ok/50 bg-emerald-50 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 size={20} className="text-ok flex-shrink-0" />
            <div>
              <div className="text-[12px] font-semibold text-ok">Incident diagnosed & recorded</div>
              <div className="text-[11px] text-sec mt-0.5">Open the Incidents page for the full report and postmortem.</div>
            </div>
          </div>
          <button onClick={handleReset}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium border border-bd text-sec bg-surface hover:text-pri rounded-md flex-shrink-0">
            <RotateCcw size={12} /> Run another
          </button>
        </motion.div>
      )}

      {/* error banner */}
      {error && (
        <div className="card p-3 border-crit bg-red-50 text-[12px] text-crit flex items-center gap-2">
          <XCircle size={15} /> {error}
        </div>
      )}

      {/* idle — pipeline overview */}
      {state === "idle" && (
        <div className="card p-5">
          <div className="text-[10px] uppercase tracking-wide text-mut font-semibold mb-4">How it works</div>
          <div className="flex items-center justify-between gap-2">
            {AGENT_ORDER.map((a, i) => {
              const meta = AGENT_META[a];
              const Icon = meta.icon;
              return (
                <div key={a} className="flex items-center gap-2 flex-1">
                  <div className="flex flex-col items-center text-center gap-1.5 flex-1">
                    <div className="w-10 h-10 rounded-full border border-bd bg-raised flex items-center justify-center">
                      <Icon size={17} className="text-sec" />
                    </div>
                    <div className="text-[11px] font-medium text-pri leading-tight">{meta.short}</div>
                    <div className="text-[10px] text-mut leading-snug">{meta.desc}</div>
                  </div>
                  {i < AGENT_ORDER.length - 1 && <ArrowRight size={15} className="text-mut/60 flex-shrink-0 mt-[-30px]" />}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
