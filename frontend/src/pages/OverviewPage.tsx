import { useEffect, useMemo, useState } from "react";
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import type { Prediction } from "../hooks/useWebSocket";
import { T, TT, ATTACK_COLOR, ATTACK_BG } from "../lib/theme";

type StatusData = {
  model:       boolean;
  prometheus:  boolean;
  loki:        boolean;
  kserve:      boolean;
  kserve_url?: string;
  num_classes?: number;
  metrics?: {
    accuracy?: number; f1?: number; f1_macro?: number;
    precision?: number; recall?: number;
  };
};

type PromData = {
  cpu_usage_percent?: number;
  memory_usage_percent?: number;
  pod_count?: number;
  node_count?: number;
  alert_count?: number;
};

function SummaryCard({
  label, value, sub, valueColor = "text-pri",
}: { label: string; value: string; sub?: string; valueColor?: string }) {
  return (
    <div className="card p-4">
      <div className="metric-label">{label}</div>
      <div className={`metric-value mt-2 ${valueColor}`}>{value}</div>
      {sub && <div className="text-[11px] text-sec mt-1">{sub}</div>}
    </div>
  );
}

export default function OverviewPage({ predictions }: { predictions: Prediction[] }) {
  const [svc,  setSvc]  = useState<StatusData | null>(null);
  const [prom, setProm] = useState<PromData>({});

  useEffect(() => {
    fetch("/api/status").then(r => r.json()).then(setSvc).catch(() => {});
    const loadMetrics = () => fetch("/api/metrics").then(r => r.json()).then(setProm).catch(() => {});
    loadMetrics();
    const iv = setInterval(loadMetrics, 10_000);
    return () => clearInterval(iv);
  }, []);

  const attacks  = predictions.filter(p => p.is_attack ?? p.prediction > 0).length;
  const rate     = predictions.length > 0 ? (attacks / predictions.length * 100).toFixed(1) : "0.0";
  const avgLat   = useMemo(() => {
    const sl = predictions.slice(0, 30);
    return sl.length ? (sl.reduce((s, p) => s + p.latency_ms, 0) / sl.length).toFixed(1) : "—";
  }, [predictions]);

  const trafficData = useMemo(() =>
    predictions.slice(0, 80).reverse().map((p, i) => ({
      i,
      normal: !p.is_attack && p.prediction === 0 ? 1 : 0,
      attack: (p.is_attack ?? p.prediction > 0) ? 1 : 0,
    })),
    [predictions]
  );

  const familyData = useMemo(() => {
    const c: Record<string, number> = {};
    predictions.forEach(p => { c[p.attack_type] = (c[p.attack_type] || 0) + 1; });
    return Object.entries(c).map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [predictions]);

  const recent = predictions.slice(0, 15);

  return (
    <div className="p-5 space-y-4">

      {/* ── Summary cards ─────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        <SummaryCard
          label="Active Nodes"
          value={`${prom.node_count ?? "—"} / 4`}
          sub="Kubernetes nodes"
        />
        <SummaryCard
          label="Flows Processed"
          value={predictions.length.toLocaleString()}
          sub="session total"
        />
        <SummaryCard
          label="Anomalies Detected"
          value={attacks.toLocaleString()}
          sub={`${rate}% threat rate`}
          valueColor={attacks > 0 ? "text-crit" : "text-ok"}
        />
        <SummaryCard
          label="Model Version"
          value="v1.0.0"
          sub="LightGBM · NSL-KDD"
        />
        <SummaryCard
          label="Detection Accuracy"
          value={svc?.metrics?.accuracy ? `${(svc.metrics.accuracy * 100).toFixed(1)}%` : "—"}
          sub={`F1 macro ${svc?.metrics ? (svc.metrics.f1_macro ?? svc.metrics.f1 ?? 0).toFixed(3) : "—"}`}
          valueColor="text-ok"
        />
        <SummaryCard
          label="Avg Latency"
          value={avgLat === "—" ? "—" : `${avgLat} ms`}
          sub="inference p50"
          valueColor={parseFloat(avgLat) > 100 ? "text-warn" : "text-pri"}
        />
      </div>

      {/* ── Charts row ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">

        {/* Traffic timeseries */}
        <div className="card xl:col-span-2">
          <div className="card-header">
            <span className="card-title">Inference Stream · Normal vs Anomaly</span>
            <span className="text-[11px] text-sec font-mono">last 80 flows · live</span>
          </div>
          <div className="p-3">
            <ResponsiveContainer width="100%" height={170}>
              <AreaChart data={trafficData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                <defs>
                  <linearGradient id="gNorm" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={T.ok}   stopOpacity={0.25} />
                    <stop offset="95%" stopColor={T.ok}   stopOpacity={0}    />
                  </linearGradient>
                  <linearGradient id="gAtk" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={T.crit} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={T.crit} stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="2 4" stroke={T.bdl} />
                <XAxis dataKey="i" hide />
                <YAxis tick={{ fill: T.mut, fontSize: 9 }} allowDecimals={false} width={20} />
                <Tooltip {...TT} />
                <Area type="monotone" dataKey="normal" stroke={T.ok}   strokeWidth={1.5} fill="url(#gNorm)" dot={false} name="Normal" />
                <Area type="monotone" dataKey="attack" stroke={T.crit} strokeWidth={1.5} fill="url(#gAtk)"  dot={false} name="Anomaly" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Attack distribution */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Attack Distribution</span>
          </div>
          <div className="p-3">
            {familyData.length === 0 ? (
              <div className="h-[170px] flex items-center justify-center text-sec text-xs">
                No data yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={170}>
                <BarChart data={familyData} layout="vertical" margin={{ top: 2, right: 32, left: 0, bottom: 2 }}>
                  <CartesianGrid strokeDasharray="2 4" stroke={T.bdl} horizontal={false} />
                  <XAxis type="number" tick={{ fill: T.mut, fontSize: 9 }} />
                  <YAxis type="category" dataKey="name" tick={{ fill: T.sec, fontSize: 10, fontFamily: "JetBrains Mono" }} width={52} />
                  <Tooltip {...TT} />
                  <Bar dataKey="value" radius={0} name="Count">
                    {familyData.map((e, i) => (
                      <Cell key={i} fill={ATTACK_COLOR[e.name] ?? T.info} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* ── Recent events table ───────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Recent Detection Events</span>
          <div className="flex items-center gap-3 text-[11px] text-sec font-mono">
            <span><span className="text-crit">{attacks}</span> alerts</span>
            <span><span className="text-pri">{predictions.length}</span> total</span>
            {predictions.length > 0 && <span className="dot dot-ok blink" />}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Source</th>
                <th>Destination</th>
                <th>Protocol</th>
                <th>Service</th>
                <th>Type</th>
                <th>Confidence</th>
                <th>Latency</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((p, i) => {
                const ts    = new Date(p.timestamp * 1000).toLocaleTimeString("en-GB");
                const isAtk = p.is_attack ?? p.prediction > 0;
                return (
                  <tr key={i} style={isAtk ? { background: ATTACK_BG[p.label] ?? "#fee2e2" } : undefined}>
                    <td className="text-sec">{ts}</td>
                    <td>{p.features.src_ip}:{p.features.src_port}</td>
                    <td className="text-sec">{p.features.dst_ip}:{p.features.dst_port}</td>
                    <td className="uppercase text-sec">{p.features.protocol}</td>
                    <td className="text-sec">{p.features.service}</td>
                    <td>
                      {isAtk
                        ? <span className="badge badge-crit">{p.label}</span>
                        : <span className="text-mut text-[11px]">—</span>}
                    </td>
                    <td>{(p.confidence * 100).toFixed(1)}%</td>
                    <td className="text-sec">{p.latency_ms} ms</td>
                    <td>
                      <span className={`badge ${isAtk ? "badge-crit" : "badge-ok"}`}>
                        {isAtk ? "THREAT" : "CLEAN"}
                      </span>
                    </td>
                  </tr>
                );
              })}
              {recent.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center text-sec py-8">
                    Waiting for inference stream…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
