import { useMemo, useState } from "react";
import type { Prediction } from "../hooks/useWebSocket";
import { ATTACK_BG } from "../lib/theme";

type Filter = "all" | "attack" | "normal";
type Family = "all" | "DoS" | "Probe" | "R2L" | "U2R";

const ATTACK_TYPES = ["neptune", "smurf", "portsweep", "ipsweep", "nmap",
                      "guess_passwd", "buffer_overflow", "rootkit"] as const;

function RiskScore({ confidence, isAtk }: { confidence: number; isAtk: boolean }) {
  const score = isAtk ? Math.round(confidence * 100) : Math.round((1 - confidence) * 30);
  const cls = score >= 80 ? "text-crit" : score >= 50 ? "text-warn" : "text-ok";
  return <span className={`font-mono text-[11px] font-semibold ${cls}`}>{score}</span>;
}

export default function ThreatDetectionPage({ predictions }: { predictions: Prediction[] }) {
  const [filter,  setFilter]  = useState<Filter>("all");
  const [family,  setFamily]  = useState<Family>("all");
  const [search,  setSearch]  = useState("");
  const [loading, setLoading] = useState<string | null>(null);
  const [lastInj, setLastInj] = useState<{ attack: string; detected: boolean; conf: number } | null>(null);

  const attacks = predictions.filter(p => p.is_attack ?? p.prediction > 0);
  const bySev = {
    critical: attacks.filter(p => p.confidence >= 0.90).length,
    high:     attacks.filter(p => p.confidence >= 0.75 && p.confidence < 0.90).length,
    medium:   attacks.filter(p => p.confidence >= 0.50 && p.confidence < 0.75).length,
    low:      attacks.filter(p => p.confidence < 0.50).length,
  };

  const rows = useMemo(() => {
    return predictions.filter(p => {
      if (filter === "attack" && !(p.is_attack ?? p.prediction > 0)) return false;
      if (filter === "normal" && (p.is_attack ?? p.prediction > 0)) return false;
      if (family !== "all" && p.attack_type !== family) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          p.features.src_ip.includes(q) ||
          p.features.dst_ip.includes(q) ||
          p.attack_type.toLowerCase().includes(q) ||
          p.features.protocol.includes(q)
        );
      }
      return true;
    }).slice(0, 200);
  }, [predictions, filter, family, search]);

  const inject = async (attack: string) => {
    setLoading(attack);
    try {
      const r = await fetch(`/api/inject?attack_type=${attack}`, { method: "POST" });
      const d = await r.json();
      setLastInj({ attack, detected: d.prediction === 1, conf: d.confidence });
    } catch {
      setLastInj(null);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="p-5 space-y-4">

      {/* ── Severity counters ─────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Critical (≥90%)",  count: bySev.critical, cls: "text-crit" },
          { label: "High (75–89%)",    count: bySev.high,     cls: "text-warn" },
          { label: "Medium (50–74%)",  count: bySev.medium,   cls: "text-info" },
          { label: "Low (<50%)",       count: bySev.low,      cls: "text-sec"  },
        ].map(s => (
          <div key={s.label} className="card p-4">
            <div className="metric-label">{s.label}</div>
            <div className={`metric-value mt-2 ${s.cls}`}>{s.count}</div>
          </div>
        ))}
      </div>

      {/* ── Filter bar ────────────────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Alert Table</span>
          <div className="flex items-center gap-2 flex-wrap">
            {(["all","attack","normal"] as Filter[]).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 text-[11px] rounded-sm border transition-colors ${
                  filter === f
                    ? "bg-acct border-acct text-pri"
                    : "bg-raised border-bd text-sec hover:text-pri"
                }`}
              >
                {f === "all" ? "All" : f === "attack" ? "Alerts only" : "Normal only"}
              </button>
            ))}
            <select
              value={family}
              onChange={e => setFamily(e.target.value as Family)}
              className="ent-input text-[11px] py-1"
            >
              <option value="all">All types</option>
              {["DoS","Probe","R2L","U2R"].map(f => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
            <input
              className="ent-input text-[11px] py-1 w-40"
              placeholder="Search IP, type…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="overflow-x-auto" style={{ maxHeight: "420px", overflowY: "auto" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Source IP</th>
                <th>Destination IP</th>
                <th>Protocol</th>
                <th>Service</th>
                <th>Attack Family</th>
                <th>Risk Score</th>
                <th>Det. Confidence</th>
                <th>Src Bytes</th>
                <th>Dst Bytes</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p, i) => {
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
                        : <span className="text-mut">—</span>}
                    </td>
                    <td><RiskScore confidence={p.confidence} isAtk={isAtk} /></td>
                    <td>{(p.confidence * 100).toFixed(1)}%</td>
                    <td className="text-sec">{p.features.src_bytes.toLocaleString()}</td>
                    <td className="text-sec">{p.features.dst_bytes.toLocaleString()}</td>
                    <td>
                      <span className={`badge ${isAtk ? "badge-crit" : "badge-ok"}`}>
                        {isAtk ? "ALERT" : "OK"}
                      </span>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={11} className="text-center text-sec py-8">
                    {predictions.length === 0 ? "Waiting for data stream…" : "No events match current filters"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="card-header border-b-0 border-t border-bd text-[11px] text-sec">
          Showing {rows.length} of {predictions.length} events
        </div>
      </div>

      {/* ── Inject test attacks ────────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Inject Test Attack</span>
          <span className="text-[11px] text-sec">Sends a synthetic flow directly to the inference engine</span>
        </div>
        <div className="p-4">
          <div className="flex flex-wrap gap-2">
            {ATTACK_TYPES.map(atk => (
              <button
                key={atk}
                onClick={() => inject(atk)}
                disabled={loading === atk}
                className="px-3 py-1.5 text-xs bg-raised border border-bd text-sec hover:text-pri hover:border-acct transition-colors rounded-sm disabled:opacity-40 font-mono"
              >
                {loading === atk ? "Sending…" : atk}
              </button>
            ))}
          </div>
          {lastInj && (
            <div className={`mt-3 p-3 text-xs font-mono border rounded-sm ${
              lastInj.detected
                ? "bg-red-50 border-crit text-crit"
                : "bg-raised border-bd text-sec"
            }`}>
              {lastInj.detected
                ? `✓ Detected: ${lastInj.attack} — confidence ${(lastInj.conf * 100).toFixed(1)}%`
                : `✗ Not detected: ${lastInj.attack} — confidence ${(lastInj.conf * 100).toFixed(1)}% (false negative)`}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
