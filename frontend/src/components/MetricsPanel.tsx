import { useEffect, useState } from "react";

type PromData = {
  cpu_usage_percent?: number;
  memory_usage_percent?: number;
  pod_count?: number;
  node_count?: number;
  alert_count?: number;
  scrape_time?: string;
};

function Bar({ pct }: { pct: number }) {
  const color = pct >= 85 ? "bg-crit" : pct >= 65 ? "bg-warn" : "bg-ok";
  return (
    <div className="progress-track flex-1">
      <div className={`progress-fill ${color}`} style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

export default function MetricsPanel() {
  const [data, setData] = useState<PromData | null>(null);
  const [age,  setAge]  = useState(0);

  useEffect(() => {
    const load = () => fetch("/api/prometheus").then(r => r.json()).then(d => { setData(d); setAge(0); }).catch(() => {});
    load();
    const iv = setInterval(load, 10_000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    const iv = setInterval(() => setAge(a => a + 1), 1000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Cluster Metrics</span>
        <span className="text-[11px] text-sec font-mono">T+{age}s</span>
      </div>
      <div className="p-3 space-y-3 text-[12px]">
        {!data && <div className="text-sec py-2">Connecting to Prometheus…</div>}
        {data && (
          <>
            <div>
              <div className="flex justify-between mb-1 text-sec">
                <span>CPU</span>
                <span className="font-mono">{data.cpu_usage_percent?.toFixed(1) ?? "—"}%</span>
              </div>
              <Bar pct={data.cpu_usage_percent ?? 0} />
            </div>
            <div>
              <div className="flex justify-between mb-1 text-sec">
                <span>Memory</span>
                <span className="font-mono">{data.memory_usage_percent?.toFixed(1) ?? "—"}%</span>
              </div>
              <Bar pct={data.memory_usage_percent ?? 0} />
            </div>
            <div className="flex justify-between text-sec pt-1 border-t border-bdl">
              <span>Pods</span>
              <span className="font-mono text-pri">{data.pod_count ?? "—"}</span>
            </div>
            <div className="flex justify-between text-sec">
              <span>Nodes</span>
              <span className="font-mono text-pri">{data.node_count ?? "—"} / 4</span>
            </div>
            <div className="flex justify-between text-sec">
              <span>Active Alerts</span>
              <span className={`font-mono ${(data.alert_count ?? 0) > 0 ? "text-warn" : "text-pri"}`}>
                {data.alert_count ?? "—"}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
