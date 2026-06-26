import type { Prediction } from "../hooks/useWebSocket";

const FAMILY_BADGE: Record<string, string> = {
  Normal: "badge-ok",
  DoS:    "badge-crit",
  Probe:  "badge-warn",
  R2L:    "badge-info",
  U2R:    "badge-purp",
};

function Row({ p }: { p: Prediction }) {
  const isAttack = p.prediction === 1;
  const ts = new Date(p.timestamp * 1000).toLocaleTimeString("en-GB");
  return (
    <tr style={isAttack ? { background: "#1e1218" } : undefined}>
      <td className="text-sec">{ts}</td>
      <td>{p.features.src_ip}:{p.features.src_port}</td>
      <td className="text-sec">{p.features.dst_ip}:{p.features.dst_port}</td>
      <td className="uppercase text-sec">{p.features.protocol}</td>
      <td className="text-sec">{p.features.service}</td>
      <td>
        {isAttack
          ? <span className={`badge ${FAMILY_BADGE[p.attack_type] ?? "badge-crit"}`}>{p.attack_type}</span>
          : <span className="text-sec">—</span>}
      </td>
      <td>{(p.confidence * 100).toFixed(1)}%</td>
      <td className="text-sec">{p.latency_ms} ms</td>
      <td>
        <span className={`badge ${isAttack ? "badge-crit" : "badge-ok"}`}>
          {isAttack ? "ALERT" : "OK"}
        </span>
      </td>
    </tr>
  );
}

export default function AnomalyFeed({ predictions }: { predictions: Prediction[] }) {
  const attacks = predictions.filter(p => p.prediction === 1).length;
  return (
    <div className="card flex flex-col h-full min-h-0">
      <div className="card-header">
        <span className="card-title">Live Detection Feed</span>
        <div className="flex items-center gap-3 text-[11px] text-sec font-mono">
          <span><span className="text-crit">{attacks}</span> alerts</span>
          <span><span className="text-pri">{predictions.length}</span> total</span>
          {predictions.length > 0 && <span className="dot dot-ok blink" />}
        </div>
      </div>
      <div className="overflow-auto flex-1 min-h-0">
        <table className="tbl">
          <thead>
            <tr>
              <th>Time</th><th>Source</th><th>Destination</th>
              <th>Proto</th><th>Service</th><th>Type</th>
              <th>Conf</th><th>Lat</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {predictions.slice(0, 100).map((p, i) => <Row key={i} p={p} />)}
            {predictions.length === 0 && (
              <tr><td colSpan={9} className="text-center text-sec py-8">Waiting for stream…</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
