import { useMemo, useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line,
} from "recharts";
import type { Prediction } from "../hooks/useWebSocket";
import { T, TT } from "../lib/theme";

type LiveStats = {
  accuracy: number; precision: number; recall: number; f1: number;
  sample_size: number; true_positives: number; false_positives: number;
  false_negatives: number; true_negatives: number; live: boolean;
};

type FIEntry = { feature: string; importance: number };

function MetricCard({ label, value, sub, color = "text-pri", live = false }: {
  label: string; value: string; sub?: string; color?: string; live?: boolean;
}) {
  return (
    <div className="card p-4 text-center">
      <div className="metric-label flex items-center justify-center gap-1.5">
        {live && <span className="dot dot-ok blink" />}
        {label}
      </div>
      <div className={`metric-value mt-2 text-[26px] ${color}`}>{value}</div>
      {sub && <div className="text-[11px] text-sec mt-1">{sub}</div>}
    </div>
  );
}

export default function ModelMonitoringPage({ predictions }: { predictions: Prediction[] }) {
  const [stats, setStats] = useState<LiveStats | null>(null);
  const [fi,    setFi]    = useState<FIEntry[]>([]);
  const [isLive, setIsLive] = useState(false);

  // Poll /api/live-stats every 5s — shows rolling accuracy from true_label
  useEffect(() => {
    const load = () =>
      fetch("/api/live-stats")
        .then(r => r.json())
        .then((d: LiveStats) => { setStats(d); setIsLive(!!d.live && d.sample_size > 20); })
        .catch(() => {});
    load();
    const iv = setInterval(load, 5_000);
    return () => clearInterval(iv);
  }, []);

  // Fetch real feature importance from the loaded model (via /api/status)
  useEffect(() => {
    fetch("/api/status")
      .then(r => r.json())
      .then(d => { if (d.feature_importance?.length) setFi(d.feature_importance); })
      .catch(() => {});
  }, []);

  const latencyData = useMemo(() =>
    predictions.slice(0, 60).reverse().map((p, i) => ({ i, ms: p.latency_ms })),
    [predictions]
  );

  const recent = predictions.slice(0, 50);
  const avgLat = recent.length
    ? (recent.reduce((s, p) => s + p.latency_ms, 0) / recent.length).toFixed(1)
    : "—";
  const p95Lat = useMemo(() => {
    if (!recent.length) return "—";
    const sorted = [...recent].map(p => p.latency_ms).sort((a, b) => a - b);
    return String(sorted[Math.floor(sorted.length * 0.95)] ?? "—");
  }, [recent]);

  const throughput = recent.length > 1
    ? (recent.length / ((recent[0].timestamp - recent[recent.length - 1].timestamp) || 1)).toFixed(2)
    : "0.00";

  const acc  = stats ? (stats.accuracy  * 100).toFixed(1) + "%" : "—";
  const prec = stats ? (stats.precision * 100).toFixed(1) + "%" : "—";
  const rec  = stats ? (stats.recall    * 100).toFixed(1) + "%" : "—";
  const f1   = stats ? stats.f1.toFixed(4)                      : "—";
  const sampleLabel = stats
    ? `${stats.sample_size} samples${isLive ? " · live" : " · training"}`
    : "loading…";

  // Confusion matrix values
  const tp = stats?.true_positives  ?? 0;
  const fp = stats?.false_positives ?? 0;
  const fn = stats?.false_negatives ?? 0;
  const tn = stats?.true_negatives  ?? 0;

  return (
    <div className="p-5 space-y-4">

      {/* ── Model info banner ─────────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Model Information</span>
          <div className="flex items-center gap-2">
            {isLive && <span className="badge badge-ok">Live Metrics</span>}
            <span className="badge badge-ok">Active</span>
          </div>
        </div>
        <div className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-x-8 gap-y-2 text-[12px]">
          {[
            ["Algorithm",   "LightGBM (GBDT)"],
            ["Version",     "v1.0.0"],
            ["Dataset",     "NSL-KDD"],
            ["Classes",     "Binary (Normal / Attack)"],
            ["Features",    "41 NSL-KDD features"],
            ["Estimators",  "300 trees"],
            ["Max Depth",   "8"],
            ["Trained",     "2026-06-08"],
          ].map(([k, v]) => (
            <div key={k}>
              <span className="text-sec">{k}: </span>
              <span className="text-pri font-mono">{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Performance metrics ──────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard label="Accuracy"  value={acc}  sub={sampleLabel}    color="text-ok"   live={isLive} />
        <MetricCard label="Precision" value={prec} sub="Attack class"    color="text-acct" live={isLive} />
        <MetricCard label="Recall"    value={rec}  sub="Attack class"    color="text-warn" live={isLive} />
        <MetricCard label="F1 Score"  value={f1}   sub="Harmonic mean"   color="text-pri"  live={isLive} />
      </div>

      {/* ── Live stats + Feature importance ──────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">

        <div className="space-y-3">

          {/* Live inference performance */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Live Inference Performance</span>
              <span className="dot dot-ok blink" />
            </div>
            <div className="p-4 grid grid-cols-3 gap-4 text-center">
              {[
                { label: "Avg Latency", value: avgLat === "—" ? "—" : `${avgLat} ms`, color: "text-pri" },
                { label: "p95 Latency", value: p95Lat === "—" ? "—" : `${p95Lat} ms`, color: parseFloat(p95Lat) > 200 ? "text-warn" : "text-pri" },
                { label: "Throughput",  value: `${throughput}/s`, color: "text-pri" },
              ].map(s => (
                <div key={s.label}>
                  <div className="metric-label">{s.label}</div>
                  <div className={`font-mono text-lg font-semibold mt-1 ${s.color}`}>{s.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Latency chart */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Inference Latency (ms) · Last 60 Flows</span>
            </div>
            <div className="p-3">
              <ResponsiveContainer width="100%" height={140}>
                <LineChart data={latencyData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="2 4" stroke={T.bdl} />
                  <XAxis dataKey="i" hide />
                  <YAxis tick={{ fill: T.mut, fontSize: 9 }} />
                  <Tooltip {...TT} formatter={(v: number) => [`${v} ms`, "Latency"]} />
                  <Line type="monotone" dataKey="ms" stroke={T.acct} strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Confusion matrix */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Confusion Matrix</span>
              <span className="text-[11px] text-sec">{sampleLabel}</span>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-2 gap-2 text-center text-[12px]">
                <div className="rounded" style={{ background: "#dcfce7", border: "1px solid #a7f3d0", padding: "12px 8px" }}>
                  <div className="text-sec mb-1">True Positive</div>
                  <div className="font-mono text-ok text-xl font-bold">{tp}</div>
                  <div className="text-[10px] text-mut mt-1">Attack → Attack ✓</div>
                </div>
                <div className="rounded" style={{ background: "#fee2e2", border: "1px solid #fca5a5", padding: "12px 8px" }}>
                  <div className="text-sec mb-1">False Positive</div>
                  <div className="font-mono text-crit text-xl font-bold">{fp}</div>
                  <div className="text-[10px] text-mut mt-1">Normal → Attack ✗</div>
                </div>
                <div className="rounded" style={{ background: "#fef3c7", border: "1px solid #fde68a", padding: "12px 8px" }}>
                  <div className="text-sec mb-1">False Negative</div>
                  <div className="font-mono text-warn text-xl font-bold">{fn}</div>
                  <div className="text-[10px] text-mut mt-1">Attack → Normal ✗</div>
                </div>
                <div className="rounded" style={{ background: "#dcfce7", border: "1px solid #a7f3d0", padding: "12px 8px" }}>
                  <div className="text-sec mb-1">True Negative</div>
                  <div className="font-mono text-ok text-xl font-bold">{tn}</div>
                  <div className="text-[10px] text-mut mt-1">Normal → Normal ✓</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Feature importance — real values from model.booster_.feature_importance */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Feature Importance · Top 10</span>
            <span className="text-[11px] text-sec">LightGBM gain · from trained model</span>
          </div>
          <div className="p-3">
            {fi.length === 0 ? (
              <div className="h-[380px] flex items-center justify-center text-sec text-xs">
                Loading feature importance…
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={380}>
                <BarChart
                  data={fi}
                  layout="vertical"
                  margin={{ top: 2, right: 50, left: 0, bottom: 2 }}
                >
                  <CartesianGrid strokeDasharray="2 4" stroke={T.bdl} horizontal={false} />
                  <XAxis
                    type="number"
                    tickFormatter={v => `${(v * 100).toFixed(0)}%`}
                    tick={{ fill: T.mut, fontSize: 9 }}
                  />
                  <YAxis
                    type="category"
                    dataKey="feature"
                    tick={{ fill: T.sec, fontSize: 10, fontFamily: "JetBrains Mono" }}
                    width={140}
                  />
                  <Tooltip
                    {...TT}
                    formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Importance"]}
                  />
                  <Bar dataKey="importance" fill={T.acct} radius={0} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
