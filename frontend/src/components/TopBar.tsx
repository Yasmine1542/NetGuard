import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import type { Page } from "./Sidebar";

const PAGE_META: Record<Page, { title: string; desc: string }> = {
  overview:  { title: "Overview",          desc: "Platform summary and live inference metrics" },
  cluster:   { title: "Cluster Status",    desc: "Kubernetes node health and resource usage" },
  threats:   { title: "Threat Detection",  desc: "Live anomaly detection feed and alert management" },
  model:     { title: "Model Monitoring",  desc: "LightGBM model performance, drift, and features" },
  logs:             { title: "Logs",            desc: "Structured log stream via Loki" },
  settings:         { title: "Settings",        desc: "Platform configuration" },
  incidents:        { title: "Incidents",       desc: "Automated incident diagnosis — root cause analysis and blameless postmortems" },
  "live-diagnosis": { title: "Live Diagnosis",  desc: "Run the 4-agent pipeline and watch each agent reason in real time" },
};

export default function TopBar({ page, wsStatus }: { page: Page; wsStatus: string }) {
  const { title, desc } = PAGE_META[page];
  const [time, setTime] = useState(() => new Date().toLocaleTimeString("en-GB"));
  const wsOk = wsStatus === "connected";

  useEffect(() => {
    const iv = setInterval(() => setTime(new Date().toLocaleTimeString("en-GB")), 1000);
    return () => clearInterval(iv);
  }, []);

  return (
    <header className="h-11 flex items-center justify-between px-5 border-b border-bd bg-panel flex-shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <h1 className="text-pri font-semibold text-sm whitespace-nowrap">{title}</h1>
        <span className="text-bdl hidden sm:block">│</span>
        <span className="text-sec text-xs hidden sm:block truncate">{desc}</span>
      </div>

      <div className="flex items-center gap-4 flex-shrink-0">
        <span className={`flex items-center gap-1.5 text-xs font-mono ${wsOk ? "text-ok" : "text-crit"}`}>
          <span className={`dot ${wsOk ? "dot-ok" : "dot-crit"}`} />
          {wsOk ? "Live" : wsStatus}
        </span>
        <span className="text-mut text-[11px] font-mono hidden md:block">
          <RefreshCw size={10} className="inline mr-1 opacity-50" />
          {time}
        </span>
      </div>
    </header>
  );
}
