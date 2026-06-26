import { useEffect, useRef, useState, useCallback } from "react";

export type Prediction = {
  prediction:          number;                                       // 0–4
  label:               "Normal" | "DoS" | "Probe" | "R2L" | "U2R"; // 5-class
  attack_type:         string;
  is_attack:           boolean;
  confidence:          number;
  class_probabilities?: Record<string, number>;
  via_kserve?:         boolean;
  latency_ms:          number;
  features: {
    protocol:  string;
    service:   string;
    src_bytes: number;
    dst_bytes: number;
    flag:      string;
    src_ip:    string;
    dst_ip:    string;
    src_port:  number;
    dst_port:  number;
  };
  true_label:  string;
  true_family?: string;
  timestamp:   number;
};

export type WsMessage =
  | { type: "prediction"; data: Prediction }
  | { type: "metrics"; data: Record<string, unknown> };

type Status = "connecting" | "connected" | "disconnected";

export function useWebSocket(url: string, maxHistory = 200) {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [clusterMetrics, setClusterMetrics] = useState<Record<string, unknown>>({});
  const [status, setStatus] = useState<Status>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("connected");
        ws.send("ping");
        const ping = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send("ping");
        }, 10000);
        (ws as any)._ping = ping;
      };

      ws.onmessage = (e) => {
        try {
          const msg: WsMessage = JSON.parse(e.data);
          if (msg.type === "prediction") {
            setPredictions((prev) => [msg.data, ...prev].slice(0, maxHistory));
          } else if (msg.type === "metrics") {
            setClusterMetrics(msg.data);
          }
        } catch {}
      };

      ws.onclose = () => {
        setStatus("disconnected");
        clearInterval((ws as any)._ping);
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      setStatus("disconnected");
      reconnectRef.current = setTimeout(connect, 3000);
    }
  }, [url, maxHistory]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { predictions, clusterMetrics, status };
}
