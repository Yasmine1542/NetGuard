import {
  LayoutDashboard, Server, Shield,
  Activity, FileText, Settings,
  BrainCircuit, Siren,
} from "lucide-react";
import type { ReactNode } from "react";

export type Page =
  | "overview" | "cluster" | "threats"
  | "model" | "logs" | "settings"
  | "incidents" | "live-diagnosis";

type NavEntry = { id: Page; label: string; icon: ReactNode; badge?: number };
type NavGroup = { label: string; items: NavEntry[] };

const NAV: NavGroup[] = [
  {
    label: "Platform",
    items: [
      { id: "overview",  label: "Overview",          icon: <LayoutDashboard size={14} /> },
      { id: "cluster",   label: "Cluster Status",    icon: <Server size={14} />          },
    ],
  },
  {
    label: "Security",
    items: [
      { id: "threats", label: "Threat Detection", icon: <Shield size={14} /> },
    ],
  },
  {
    label: "MLOps",
    items: [
      { id: "model", label: "Model Monitoring", icon: <Activity size={14} /> },
    ],
  },
  {
    label: "AIOps",
    items: [
      { id: "incidents",       label: "Incidents",       icon: <Siren size={14} />        },
      { id: "live-diagnosis",  label: "Live Diagnosis",  icon: <BrainCircuit size={14} /> },
    ],
  },
  {
    label: "Observability",
    items: [
      { id: "logs", label: "Logs", icon: <FileText size={14} /> },
    ],
  },
];

type Props = { active: Page; onNavigate: (p: Page) => void; wsStatus: string; openIncidents?: number };

export default function Sidebar({ active, onNavigate, wsStatus, openIncidents = 0 }: Props) {
  const wsOk = wsStatus === "connected";

  return (
    <aside className="w-[220px] flex-shrink-0 flex flex-col bg-panel border-r border-bd overflow-y-auto">
      {/* Brand */}
      <div className="px-4 py-3.5 border-b border-bdl" style={{ borderTop: "3px solid #1a56db" }}>
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded flex-shrink-0 flex items-center justify-center" style={{ background: "#1a56db" }}>
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
              <path d="M6 1L11 4v4L6 11 1 8V4L6 1z" stroke="white" strokeWidth="1.4" fill="none" />
              <circle cx="6" cy="6" r="1.5" fill="white" />
            </svg>
          </div>
          <div>
            <div className="text-pri font-semibold text-sm leading-tight">NetGuard NIC</div>
            <div className="text-mut text-[9px] font-mono leading-tight">Network Intelligence Center</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-1">
        {NAV.map(group => (
          <div key={group.label}>
            <div className="nav-section">{group.label}</div>
            {group.items.map(item => (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`nav-item ${active === item.id ? "active" : ""}`}
              >
                <span className="text-mut flex-shrink-0">{item.icon}</span>
                <span className="flex-1 text-left">{item.label}</span>
                {item.id === "incidents" && openIncidents > 0 && (
                  <span className="ml-auto text-[9px] font-bold bg-crit text-white
                                   rounded-full min-w-[16px] h-4 flex items-center
                                   justify-center px-1 leading-none">
                    {openIncidents}
                  </span>
                )}
              </button>
            ))}
          </div>
        ))}

        <div className="divider my-2" />
        <button
          onClick={() => onNavigate("settings")}
          className={`nav-item ${active === "settings" ? "active" : ""}`}
        >
          <span className="text-mut flex-shrink-0"><Settings size={14} /></span>
          Settings
        </button>
      </nav>

      {/* Connection status */}
      <div className="border-t border-bdl px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className={`dot ${wsOk ? "dot-ok" : wsStatus === "connecting" ? "dot-warn" : "dot-crit"}`} />
          <span className="text-[10px] text-sec font-mono">
            {wsOk ? "Stream live" : wsStatus === "connecting" ? "Connecting…" : "Disconnected"}
          </span>
        </div>
        <div className="text-[10px] text-mut mt-0.5">{`${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws`}</div>
      </div>
    </aside>
  );
}
