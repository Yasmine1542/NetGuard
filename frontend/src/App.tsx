import { useState, useEffect, useCallback } from "react";
import Sidebar, { type Page } from "./components/Sidebar";
import TopBar from "./components/TopBar";
import { useWebSocket } from "./hooks/useWebSocket";
import OverviewPage from "./pages/OverviewPage";
import ThreatDetectionPage from "./pages/ThreatDetectionPage";
import ModelMonitoringPage from "./pages/ModelMonitoringPage";
import ClusterStatusPage from "./pages/ClusterStatusPage";
import LogsPage from "./pages/LogsPage";
import IncidentsPage from "./pages/IncidentsPage";
import LiveDiagnosisPage from "./pages/LiveDiagnosisPage";

const WS_URL = `ws://${window.location.host}/ws`;

export default function App() {
  const [page, setPage]                   = useState<Page>("overview");
  const [openIncidents, setOpenIncidents] = useState(0);
  const { predictions, status }           = useWebSocket(WS_URL);

  // Poll open incident count for sidebar badge
  const fetchOpenCount = useCallback(async () => {
    try {
      const r = await fetch("/api/incidents?status=OPEN&limit=100");
      const d = await r.json();
      setOpenIncidents(Array.isArray(d) ? d.length : 0);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchOpenCount();
    const id = setInterval(fetchOpenCount, 15_000);
    return () => clearInterval(id);
  }, [fetchOpenCount]);

  const content = () => {
    switch (page) {
      case "overview":        return <OverviewPage predictions={predictions} />;
      case "cluster":         return <ClusterStatusPage />;
      case "threats":         return <ThreatDetectionPage predictions={predictions} />;
      case "model":           return <ModelMonitoringPage predictions={predictions} />;
      case "logs":            return <LogsPage />;
      case "incidents":       return <IncidentsPage />;
      case "live-diagnosis":  return (
        <LiveDiagnosisPage
          onIncidentCreated={() => {
            fetchOpenCount();
          }}
        />
      );
      case "settings":        return <SettingsPage />;
      default:                return <OverviewPage predictions={predictions} />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-base text-pri font-sans text-sm">
      <Sidebar
        active={page}
        onNavigate={setPage}
        wsStatus={status}
        openIncidents={openIncidents}
      />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <TopBar page={page} wsStatus={status} />
        <main className="flex-1 overflow-y-auto bg-base">{content()}</main>
      </div>
    </div>
  );
}

function SettingsPage() {
  return (
    <div className="p-6 text-sec text-sm">
      <p className="font-semibold text-pri mb-1">Settings</p>
      <p>Configuration options — coming in a future release.</p>
    </div>
  );
}
