import { useState } from "react";

const ATTACKS = ["neptune","smurf","portsweep","ipsweep","nmap","guess_passwd","buffer_overflow","rootkit"] as const;

export default function InjectPanel() {
  const [loading, setLoading] = useState<string | null>(null);
  const [last,    setLast]    = useState<{ attack: string; detected: boolean; conf: number } | null>(null);

  const inject = async (attack: string) => {
    setLoading(attack);
    try {
      const r = await fetch(`/api/inject?attack_type=${attack}`, { method: "POST" });
      const d = await r.json();
      setLast({ attack, detected: d.prediction === 1, conf: d.confidence });
    } catch {
      setLast(null);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Inject Test Attack</span>
      </div>
      <div className="p-4 space-y-3">
        <div className="flex flex-wrap gap-2">
          {ATTACKS.map(atk => (
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
        {last && (
          <div className={`p-3 text-xs font-mono border rounded-sm ${
            last.detected ? "bg-red-50 border-crit text-crit" : "bg-raised border-bd text-sec"
          }`}>
            {last.detected
              ? `✓ Detected: ${last.attack} (${(last.conf * 100).toFixed(1)}% confidence)`
              : `✗ Not detected: ${last.attack} — false negative`}
          </div>
        )}
      </div>
    </div>
  );
}
