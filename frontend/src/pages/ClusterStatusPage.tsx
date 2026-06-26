import { useEffect, useState } from "react";

type Metrics = {
  cpu_usage_percent?: number;
  memory_usage_percent?: number;
  pod_count?: number;
  node_count?: number;
  alert_count?: number;
};

type NodeInfo = { name: string; ip: string; role: string; version: string; ready: boolean };
type NsInfo   = { name: string; pods: number };

type Cluster = {
  nodes_total?: number;
  nodes_ready?: number;
  pods_total?: number;
  pods_unhealthy?: number;
  namespaces?: number;
  nodes?: NodeInfo[];
  namespace_pods?: NsInfo[];
};

function GaugeBar({ pct }: { pct: number }) {
  const w = Math.round(Math.min(100, pct));
  const color = pct >= 85 ? "bg-crit" : pct >= 65 ? "bg-warn" : "bg-ok";
  return (
    <div className="flex items-center gap-2">
      <div className="progress-track flex-1">
        <div className={`progress-fill ${color}`} style={{ width: `${w}%` }} />
      </div>
      <span className="text-[11px] font-mono text-sec w-10 text-right">{pct.toFixed(1)}%</span>
    </div>
  );
}

export default function ClusterStatusPage() {
  const [prom, setProm]       = useState<Metrics>({});
  const [cluster, setCluster] = useState<Cluster>({});
  const [age,  setAge]        = useState(0);

  useEffect(() => {
    const load = () => {
      fetch("/api/metrics").then(r => r.json()).then(d => { setProm(d); setAge(0); }).catch(() => {});
      fetch("/api/cluster").then(r => r.json()).then(setCluster).catch(() => {});
    };
    load();
    const iv = setInterval(load, 10_000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    const iv = setInterval(() => setAge(a => a + 1), 1000);
    return () => clearInterval(iv);
  }, []);

  const nodes      = cluster.nodes ?? [];
  const namespaces = cluster.namespace_pods ?? [];
  const podCap     = (cluster.nodes_total ?? 0) * 110;  // kubelet default max-pods

  return (
    <div className="p-5 space-y-4">

      {/* ── Top metrics ───────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {[
          { label: "Running Pods",  value: cluster.pods_total ?? prom.pod_count ?? "—", unit: "" },
          { label: "Nodes Ready",   value: cluster.nodes_ready ?? "—", unit: `/ ${cluster.nodes_total ?? "—"}` },
          { label: "Unhealthy Pods", value: cluster.pods_unhealthy ?? "—", unit: "" },
          { label: "CPU Usage",     value: prom.cpu_usage_percent   ? `${prom.cpu_usage_percent.toFixed(1)}%`   : "—", unit: "" },
          { label: "Memory Usage",  value: prom.memory_usage_percent ? `${prom.memory_usage_percent.toFixed(1)}%` : "—", unit: "" },
        ].map(s => (
          <div key={s.label} className="card p-4">
            <div className="metric-label">{s.label}</div>
            <div className="metric-value mt-2 text-pri">
              {s.value}<span className="text-sec text-sm ml-1">{s.unit}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">

        {/* ── Node table ───────────────────────────────────────── */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Node Status</span>
            <span className="text-[11px] text-sec font-mono">T+{age}s since last poll</span>
          </div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Node</th>
                <th>IP Address</th>
                <th>Role</th>
                <th>k8s Version</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {nodes.length === 0 ? (
                <tr><td colSpan={5} className="text-sec text-center py-4">Loading nodes…</td></tr>
              ) : nodes.map(n => (
                <tr key={n.name}>
                  <td className="font-semibold text-pri">{n.name}</td>
                  <td>{n.ip}</td>
                  <td className="col-label capitalize">{n.role}</td>
                  <td>{n.version}</td>
                  <td>
                    <span className={`badge ${n.ready ? "badge-ok" : "badge-crit"}`}>
                      {n.ready ? "Ready" : "NotReady"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ── Resource utilisation ─────────────────────────────── */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Resource Utilisation</span>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <div className="flex justify-between text-[12px] mb-1.5">
                <span className="text-sec">CPU (cluster-wide)</span>
              </div>
              <GaugeBar pct={prom.cpu_usage_percent ?? 0} />
            </div>
            <div>
              <div className="flex justify-between text-[12px] mb-1.5">
                <span className="text-sec">Memory (cluster-wide)</span>
              </div>
              <GaugeBar pct={prom.memory_usage_percent ?? 0} />
            </div>
            <div>
              <div className="flex justify-between text-[12px] mb-1.5">
                <span className="text-sec">Pod capacity</span>
                <span className="text-sec text-[11px] font-mono">{cluster.pods_total ?? 0} / {podCap || "—"}</span>
              </div>
              <GaugeBar pct={podCap ? ((cluster.pods_total ?? 0) / podCap) * 100 : 0} />
            </div>
          </div>
        </div>
      </div>

      {/* ── Namespace table ───────────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Namespaces</span>
          <span className="text-[11px] text-sec font-mono">{namespaces.length} active</span>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th>Namespace</th>
              <th>Pods</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {namespaces.length === 0 ? (
              <tr><td colSpan={3} className="text-sec text-center py-4">Loading namespaces…</td></tr>
            ) : namespaces.map(ns => (
              <tr key={ns.name}>
                <td className="font-mono text-pri">{ns.name}</td>
                <td>{ns.pods}</td>
                <td><span className="badge badge-ok">Active</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
