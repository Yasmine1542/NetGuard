import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { useMemo } from "react";
import type { Prediction } from "../hooks/useWebSocket";
import { T, TT, ATTACK_COLOR } from "../lib/theme";

export function LatencyChart({ predictions }: { predictions: Prediction[] }) {
  const data = useMemo(() =>
    predictions.slice(0, 60).reverse().map((p, i) => ({ i, ms: p.latency_ms })),
    [predictions]
  );
  return (
    <div className="card">
      <div className="card-header"><span className="card-title">Inference Latency (ms)</span></div>
      <div className="p-3">
        <ResponsiveContainer width="100%" height={120}>
          <AreaChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
            <defs>
              <linearGradient id="latG" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={T.acct} stopOpacity={0.2} />
                <stop offset="95%" stopColor={T.acct} stopOpacity={0}   />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="2 4" stroke={T.bdl} />
            <XAxis dataKey="i" hide />
            <YAxis tick={{ fill: T.mut, fontSize: 9 }} />
            <Tooltip {...TT} formatter={(v: number) => [`${v} ms`, "Latency"]} />
            <Area type="step" dataKey="ms" stroke={T.acct} strokeWidth={1.5} fill="url(#latG)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function AnomalyRateChart({ predictions }: { predictions: Prediction[] }) {
  const data = useMemo(() => {
    const b: { t: string; normal: number; attack: number }[] = [];
    for (let i = 0; i < Math.min(predictions.length, 100); i += 10) {
      const sl = predictions.slice(i, i + 10);
      const at = sl.filter(p => p.prediction === 1).length;
      b.unshift({ t: `T${Math.floor(i / 10) + 1}`, normal: sl.length - at, attack: at });
    }
    return b;
  }, [predictions]);
  return (
    <div className="card">
      <div className="card-header"><span className="card-title">Traffic Breakdown · Per 10 Flows</span></div>
      <div className="p-3">
        <ResponsiveContainer width="100%" height={120}>
          <BarChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
            <CartesianGrid strokeDasharray="2 4" stroke={T.bdl} />
            <XAxis dataKey="t" tick={{ fill: T.sec, fontSize: 9 }} />
            <YAxis tick={{ fill: T.mut, fontSize: 9 }} />
            <Tooltip {...TT} />
            <Bar dataKey="normal" stackId="a" fill={T.ok}   name="Normal" />
            <Bar dataKey="attack" stackId="a" fill={T.crit} name="Attack" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function AttackDonut({ predictions }: { predictions: Prediction[] }) {
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    predictions.forEach(p => { c[p.attack_type] = (c[p.attack_type] || 0) + 1; });
    return Object.entries(c).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  }, [predictions]);
  const total = predictions.length || 1;
  return (
    <div className="card">
      <div className="card-header"><span className="card-title">Attack Breakdown</span></div>
      <div className="p-4 space-y-2">
        {counts.slice(0, 8).map((e, i) => {
          const pct = (e.value / total) * 100;
          const color = ATTACK_COLOR[e.name] ?? T.info;
          return (
            <div key={i} className="flex items-center gap-2 text-[12px]">
              <span className="w-14 truncate text-sec font-mono text-[10px]">{e.name}</span>
              <div className="progress-track flex-1">
                <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
              </div>
              <span className="text-sec font-mono w-10 text-right text-[11px]">{pct.toFixed(1)}%</span>
            </div>
          );
        })}
        {counts.length === 0 && <span className="text-sec text-sm">No data</span>}
      </div>
    </div>
  );
}
