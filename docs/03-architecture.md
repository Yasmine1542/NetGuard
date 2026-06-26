# NetGuard — Architecture Design

## Current Architecture (As-Is)

```mermaid
graph TB
    subgraph "Local Machine (dev)"
        SIM["Simulation Loop\nbcast every 2s\n(fake NSL-KDD records)"]
        BE["FastAPI Backend\nlocalhost:8000"]
        FE["React Frontend\nlocalhost:3000"]
        MDL["LightGBM Model\nloaded in-memory"]
        SIM --> BE
        MDL --> BE
        BE -->|"WebSocket /ws"| FE
    end

    subgraph "Not Connected"
        PROM["Prometheus\n❌ PROMETHEUS_URL empty"]
        LOKI["Loki\n❌ LOKI_URL empty"]
        OPNS["OPNsense 10.0.0.1\n❌ no collector"]
    end

    style SIM fill:#2a0f0f,color:#c04848
    style PROM fill:#2a1f08,color:#b08030
    style LOKI fill:#2a1f08,color:#b08030
    style OPNS fill:#2a1f08,color:#b08030
```

**Problems with this:**
- All data is synthetic — model runs on fake flows
- No persistence — restart loses everything
- `/api/metrics` returns 422 (missing query param)
- Cluster Status and MetricsPanel are broken
- `true_label` is generated but never used for live accuracy
- Model loaded once at startup, no hot-reload or versioning

---

## Target Architecture (To-Be)

```mermaid
graph TB
    subgraph "Data Sources"
        OPNS["OPNsense\n10.0.0.1\npf state table"]
        SIM2["Simulation Service\n(background, labeled)\nfor model validation"]
    end

    subgraph "Ingestion Layer"
        COL["Flow Collector\ncollector/opnsense_collector.py\nSSH → pfctl → feature extraction"]
        FE2["Feature Engineer\n41 NSL-KDD features\nrolling window stats"]
    end

    subgraph "Inference Layer"
        API["FastAPI\n/api/ingest  POST\n/api/metrics GET\n/api/live-stats GET\n/ws WebSocket"]
        MDL2["LightGBM v1.0.0\nloaded from MLflow\nhot-reloadable"]
        KSERVE["KServe InferenceService\n(production path)\ncanary-aware"]
    end

    subgraph "Storage Layer"
        REDIS["Redis\nlast 10k alerts\nreal-time pub/sub"]
        PG["PostgreSQL\nlong-term alert history\nmodel run log"]
        MINIO["MinIO\nmodel artifacts\ntraining datasets"]
    end

    subgraph "MLOps Layer"
        MLFLOW["MLflow\nExperiment tracking\nModel registry"]
        ARGOWF["Argo Workflows\nTraining DAG"]
        ARGORL["Argo Rollouts\nCanary deployment"]
        PUSH["Pushgateway\nExposes F1 for\nAnalysisTemplate"]
    end

    subgraph "Observability"
        PROM2["Prometheus\nkube-prometheus-stack"]
        LOKI2["Loki + Alloy\nlog aggregation"]
    end

    subgraph "Frontend"
        DSH["React Dashboard\nWebSocket + REST"]
    end

    OPNS -->|"SSH poll 2s"| COL
    COL --> FE2
    SIM2 -->|"labeled flows"| FE2
    FE2 -->|"POST /api/ingest\nsource=real|sim"| API
    API --> MDL2
    API --> REDIS
    REDIS -->|"WebSocket broadcast"| DSH
    PG -.->|"history queries"| DSH
    PROM2 -->|"GET /api/metrics"| API
    LOKI2 -->|"GET /api/loki"| API
    API -->|"metrics + results"| DSH

    ARGOWF -->|"training artifact"| MINIO
    MINIO -->|"model.pkl"| MLFLOW
    MLFLOW -->|"Production model"| MDL2
    MLFLOW -->|"Canary model"| KSERVE
    MDL2 -->|"F1 score"| PUSH
    PUSH -->|"AnalysisTemplate"| ARGORL
    ARGORL -->|"traffic split"| API

    style OPNS fill:#0d2a1c,color:#3b9e70
    style SIM2 fill:#1f2435,color:#8890a4
```

---

## Component Specifications

### 1. Flow Collector (`collector/opnsense_collector.py`)

**Responsibility:** Bridge OPNsense pf state table → NSL-KDD feature vectors

```
Input:  pfctl -s states -v  (SSH, every 2s)
Output: POST /api/ingest    (JSON, 41 features + metadata)
```

**Feature extraction logic:**

| NSL-KDD Feature | Source |
|----------------|--------|
| `protocol_type` | pf state proto field |
| `service` | dst_port → service map (80→http, 22→ssh…) |
| `flag` | pf TCP state → SF/S0/REJ/RSTO |
| `src_bytes` | pf state byte counter (from -v) |
| `dst_bytes` | pf state byte counter |
| `duration` | pf state age field |
| `count` | connections to same dst in last 2s (rolling window) |
| `srv_count` | connections to same service in last 2s |
| `serror_rate` | fraction SYN-error states in last 2s |
| `dst_host_count` | connections to same dst in last 100 flows |
| `dst_host_srv_count` | same service + same dst in last 100 |
| All others | Conservative defaults (0) |

**State tracking:**
- `seen_keys: set` — deduplication across polls (key = proto+src+dst+ports)
- `recent_window: deque(maxlen=1000)` — rolling stats for statistical features
- Flush `seen_keys` every 60s to capture re-connections

---

### 2. Backend API — New/Fixed Endpoints

| Endpoint | Method | Status | Action |
|----------|--------|--------|--------|
| `/api/ingest` | POST | ❌ Missing | Accept raw flow dict → inference → broadcast → persist |
| `/api/metrics` | GET | ❌ Missing | Return `{cpu%, memory%, pod_count, node_count}` via psutil + kubectl |
| `/api/live-stats` | GET | ❌ Missing | Rolling precision/recall/F1 from simulated stream (ground truth available) |
| `/api/alerts` | GET | ❌ Missing | Query persisted alert history (time range, filters) |
| `/api/prometheus` | GET | ⚠️ Broken | Requires `query` param — frontend was calling with no params |

**Live accuracy tracking:**
```python
# Rolling window of (predicted, true_binary) from simulated stream only
# Real flows: true_label = "unknown" → excluded from accuracy computation
accuracy_window = deque(maxlen=500)

# Metrics updated on every simulated prediction
def compute_live_stats():
    tp = sum(p==1 and t==1 for p,t in accuracy_window)
    fp = sum(p==1 and t==0 for p,t in accuracy_window)
    fn = sum(p==0 and t==1 for p,t in accuracy_window)
    tn = sum(p==0 and t==0 for p,t in accuracy_window)
    precision = tp / (tp + fp) if tp+fp > 0 else 0
    recall    = tp / (tp + fn) if tp+fn > 0 else 0
    f1        = 2*precision*recall / (precision+recall) if precision+recall > 0 else 0
    return {precision, recall, f1, accuracy=(tp+tn)/len(window)}
```

---

### 3. Storage Layer

**Phase 1 (current sprint):** In-memory only — extend to 10k alert deque
**Phase 2:** Redis for pub/sub and short-term history (TTL 24h)
**Phase 3:** PostgreSQL for long-term history, alert acknowledgement, user notes

Schema (Phase 3):
```sql
CREATE TABLE alerts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL,
    src_ip      INET,
    dst_ip      INET,
    src_port    INTEGER,
    dst_port    INTEGER,
    protocol    TEXT,
    service     TEXT,
    prediction  INTEGER,     -- 0 or 1
    attack_type TEXT,
    confidence  NUMERIC(5,4),
    latency_ms  NUMERIC(8,2),
    source      TEXT,        -- 'real' | 'simulated' | 'injected'
    true_label  TEXT,        -- known only for simulated/injected
    status      TEXT DEFAULT 'open'  -- open | acknowledged | suppressed
);

CREATE INDEX ON alerts (timestamp DESC);
CREATE INDEX ON alerts (src_ip, timestamp DESC);
CREATE INDEX ON alerts (prediction, timestamp DESC);
```

---

### 4. MLOps Pipeline — Data Flow

```mermaid
sequenceDiagram
    participant DEV as MLOps Engineer
    participant AZ  as Azure Pipelines
    participant ARGO as Argo Workflows
    participant MLF  as MLflow
    participant MINIO as MinIO
    participant ROLL  as Argo Rollouts
    participant INF   as Inference Service

    DEV->>AZ: git push to main
    AZ->>AZ: lint + unit tests
    AZ->>ARGO: trigger training DAG
    ARGO->>ARGO: download NSL-KDD
    ARGO->>ARGO: train LightGBM
    ARGO->>ARGO: evaluate on test set
    ARGO->>MLF: log metrics + params
    ARGO->>MINIO: upload model.pkl
    ARGO->>MLF: register model version
    alt F1 >= 0.75
        MLF->>ROLL: trigger canary rollout
        ROLL->>INF: shift 10% traffic to new version
        ROLL->>ROLL: run AnalysisTemplate (F1 from Pushgateway)
        alt analysis passes for 5min
            ROLL->>INF: promote to 100%
        else analysis fails
            ROLL->>INF: rollback to previous version
        end
    else F1 < 0.75
        MLF-->>DEV: notify — model rejected
    end
```

---

## Build Order (Prioritised)

```mermaid
graph LR
    P1["Phase 1\nBackend fixes\n─────────────\n/api/metrics\n/api/ingest\n/api/live-stats\nsource tagging\n─────────────\n~4h"]
    P2["Phase 2\nFlow Collector\n─────────────\nSSH pfctl parser\nFeature extractor\nState tracker\nPOST /api/ingest\n─────────────\n~6h"]
    P3["Phase 3\nPersistence\n─────────────\nRedis pub/sub\nAlert history deque\nCSV export\nAcknowledge\n─────────────\n~4h"]
    P4["Phase 4\nMLOps pipeline\n─────────────\nArgo Workflows DAG\nMLflow tracking\nKServe manifest\nArgo Rollouts\n─────────────\n~1d"]
    P5["Phase 5\nFull observability\n─────────────\nPrometheus scrape\nLoki integration\nDrift detection\nSHAP values\n─────────────\n~1d"]

    P1 --> P2 --> P3 --> P4 --> P5

    style P1 fill:#0d2a1c,color:#3b9e70
    style P2 fill:#0e1c38,color:#3870b8
    style P3 fill:#271c08,color:#b08030
    style P4 fill:#1a1030,color:#7060a8
    style P5 fill:#1f2435,color:#8890a4
```

---

## Key Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Inference runtime** | FastAPI (dev) → KServe (prod) | FastAPI is fast to iterate; KServe gives canary, autoscaling, A/B |
| **Feature store** | None (stateless) | NSL-KDD features computed per-flow; no cross-flow features needed in real-time path |
| **Message queue** | None (Phase 1–3) → Redis Streams (Phase 4) | Direct HTTP is sufficient for 500 flows/s; queue needed only for burst buffering |
| **Model hot-reload** | Endpoint `/api/reload` | Avoids restart; new model loaded into memory atomically via Python threading.Lock |
| **Source tagging** | `source: real | simulated | injected` | Separates ground-truth stream (simulated) from unknown-truth stream (real) for accurate live metrics |
| **Accuracy computation** | Simulated stream only | Real OPNsense traffic has no ground truth; computing "accuracy" on it would be meaningless |
| **Canary gate** | F1 ≥ 0.75 for 5 min | Conservative threshold — network security prefers high precision over recall |
