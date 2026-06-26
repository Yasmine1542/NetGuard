# NetGuard — Use Case Catalog

## Use Case Map by Actor

```mermaid
graph LR
    A1(["👤 Security Analyst"])
    A2(["👤 MLOps Engineer"])
    A3(["👤 Platform Admin"])
    A4(["⚙️ OPNsense"])
    A5(["⚙️ K8s Cluster"])
    A6(["⚙️ CI/CD System"])

    %% Security Analyst use cases
    A1 --> UC01["UC-01\nView live detection feed"]
    A1 --> UC02["UC-02\nInvestigate flagged flow"]
    A1 --> UC03["UC-03\nFilter alerts by severity / type"]
    A1 --> UC04["UC-04\nInject synthetic attack"]
    A1 --> UC05["UC-05\nExport alert history"]
    A1 --> UC06["UC-06\nAcknowledge / suppress alert"]

    %% MLOps Engineer use cases
    A2 --> UC10["UC-10\nTrigger model training run"]
    A2 --> UC11["UC-11\nCompare model versions"]
    A2 --> UC12["UC-12\nPromote model to production"]
    A2 --> UC13["UC-13\nStart canary rollout"]
    A2 --> UC14["UC-14\nMonitor canary metrics"]
    A2 --> UC15["UC-15\nRollback model version"]
    A2 --> UC16["UC-16\nView drift indicators"]
    A2 --> UC17["UC-17\nView feature importance"]

    %% Platform Admin
    A3 --> UC20["UC-20\nView cluster node status"]
    A3 --> UC21["UC-21\nView infrastructure metrics"]
    A3 --> UC22["UC-22\nQuery application logs"]
    A3 --> UC23["UC-23\nConfigure collector source"]

    %% External system triggers
    A4 --> UC30["UC-30\nStream network flows"]
    A5 --> UC31["UC-31\nProvide cluster telemetry"]
    A6 --> UC32["UC-32\nTrigger CI pipeline"]
    A6 --> UC33["UC-33\nDeploy model artifact"]

    %% Include relationships
    UC02 -.->|includes| UC01
    UC03 -.->|includes| UC01
    UC14 -.->|includes| UC13
    UC15 -.->|extends|  UC13
    UC11 -.->|includes| UC10
    UC12 -.->|includes| UC11

    style A1 fill:#1f2435,color:#d8dce8
    style A2 fill:#1f2435,color:#d8dce8
    style A3 fill:#1f2435,color:#d8dce8
    style A4 fill:#252c3c,color:#8890a4
    style A5 fill:#252c3c,color:#8890a4
    style A6 fill:#252c3c,color:#8890a4
```

---

## Detailed Use Cases

### Security Domain

---

#### UC-01 — View Live Detection Feed
| Field | Value |
|-------|-------|
| **Actor** | Security Analyst |
| **Trigger** | Dashboard opened / WebSocket connects |
| **Precondition** | Inference engine running, collector sending flows |
| **Main Flow** | 1. Collector sends NSL-KDD vector → 2. Model runs inference → 3. Result broadcast via WebSocket → 4. Dashboard row appended in real time |
| **Alternate Flow** | If collector is down: simulated flows continue; indicator shows `[SIM]` source tag |
| **Postcondition** | Feed shows last N flows with source IP, dst IP, protocol, attack type, confidence, latency |
| **Current state** | ✅ Implemented (simulated source only) |
| **Gap** | ❌ No `source` tag distinguishing real vs simulated; ❌ no persistence |

---

#### UC-02 — Investigate Flagged Flow
| Field | Value |
|-------|-------|
| **Actor** | Security Analyst |
| **Trigger** | Analyst clicks on an ALERT row in the feed |
| **Precondition** | UC-01 active, alert exists |
| **Main Flow** | 1. Row expands to show all 41 NSL-KDD features → 2. Shows which features contributed most (SHAP) → 3. Shows similar past alerts from same src IP |
| **Current state** | ❌ Not implemented — rows are static, no detail view |
| **Gap** | ❌ No expandable row; ❌ no SHAP values; ❌ no IP history lookup |

---

#### UC-03 — Filter Alerts by Severity / Type
| Field | Value |
|-------|-------|
| **Actor** | Security Analyst |
| **Trigger** | Analyst selects filter in Threat Detection page |
| **Main Flow** | Client-side filter on `attack_type`, `confidence` threshold, `source` (real/simulated), `time range` |
| **Current state** | ✅ Partially implemented (filter by type, status); ❌ no time range; ❌ no confidence slider |

---

#### UC-04 — Inject Synthetic Attack
| Field | Value |
|-------|-------|
| **Actor** | Security Analyst |
| **Trigger** | Analyst clicks attack button in Threat Detection page |
| **Main Flow** | 1. POST `/api/inject?attack_type=neptune` → 2. Backend generates synthetic flow with that label → 3. Model runs inference → 4. Result broadcast |
| **Purpose** | Validate model is active and detecting expected attack families |
| **Current state** | ✅ Implemented |
| **Gap** | ❌ No feedback if model fails to detect (false negative should be highlighted) |

---

#### UC-05 — Export Alert History
| Field | Value |
|-------|-------|
| **Actor** | Security Analyst |
| **Trigger** | "Export CSV" button on Threat Detection page |
| **Main Flow** | 1. Query alert store for time range → 2. Serialize to CSV/JSON → 3. Browser download |
| **Current state** | ❌ Not implemented |
| **Gap** | ❌ No persistence layer; alerts disappear on page refresh |

---

#### UC-06 — Acknowledge / Suppress Alert
| Field | Value |
|-------|-------|
| **Actor** | Security Analyst |
| **Trigger** | Analyst marks alert as reviewed |
| **Main Flow** | Alert status changes from `OPEN` → `ACKNOWLEDGED`, persisted in database |
| **Current state** | ❌ Not implemented |

---

### MLOps Domain

---

#### UC-10 — Trigger Model Training Run
| Field | Value |
|-------|-------|
| **Actor** | MLOps Engineer / CI/CD System |
| **Trigger** | Manual trigger in CI/CD page OR push to `main` branch |
| **Main Flow** | 1. Argo Workflows DAG starts → 2. Downloads NSL-KDD dataset → 3. Trains LightGBM → 4. Evaluates on test set → 5. Logs metrics + artifact to MLflow → 6. Registers model if F1 ≥ threshold |
| **Current state** | ❌ Training is a local script (`model/train.py`), no orchestration |
| **Gap** | ❌ No Argo Workflows DAG; ❌ No MLflow tracking; ❌ No automated trigger |

---

#### UC-11 — Compare Model Versions
| Field | Value |
|-------|-------|
| **Actor** | MLOps Engineer |
| **Trigger** | Navigate to Model Monitoring → version comparison view |
| **Main Flow** | Fetch run list from MLflow API → display accuracy/F1/latency side by side per version |
| **Current state** | ❌ Not implemented — metrics are static from training artifacts |

---

#### UC-12 — Promote Model to Production
| Field | Value |
|-------|-------|
| **Actor** | MLOps Engineer |
| **Trigger** | "Promote" button after canary analysis passes |
| **Precondition** | Canary deployment running, AnalysisTemplate passing |
| **Main Flow** | 1. Argo Rollouts sets canary weight to 100% → 2. Old version scaled to 0 → 3. KServe InferenceService updated → 4. MLflow model stage → `Production` |
| **Current state** | ❌ CI/CD page shows mock data only |

---

#### UC-13 — Start Canary Rollout
| Field | Value |
|-------|-------|
| **Actor** | MLOps Engineer / CI/CD System |
| **Trigger** | New model image pushed to registry |
| **Main Flow** | 1. ArgoCD detects new image tag → 2. Argo Rollouts shifts 10% traffic to canary → 3. AnalysisTemplate reads F1 from Pushgateway → 4. Auto-promotes if F1 ≥ 0.75 for 5 min; auto-rollbacks if F1 < 0.65 |
| **Current state** | ❌ CI/CD page shows mock — no real Argo Rollouts integration |

---

#### UC-16 — View Drift Indicators
| Field | Value |
|-------|-------|
| **Actor** | MLOps Engineer |
| **Trigger** | Navigate to Model Monitoring → Drift section |
| **Main Flow** | Backend computes KL-divergence between training feature distribution and last N real flows; PSI score; displays per-feature drift chart |
| **Current state** | ❌ Hardcoded static values |
| **Gap** | ❌ No feature distribution storage; ❌ no KL computation |

---

### Platform Administration Domain

---

#### UC-20 — View Cluster Node Status
| Field | Value |
|-------|-------|
| **Actor** | Platform Admin |
| **Trigger** | Navigate to Cluster Status page |
| **Main Flow** | Backend queries `kubectl get nodes` or Kubernetes API → returns node list with status, version, IP |
| **Current state** | ❌ Hardcoded static list of 4 nodes |
| **Gap** | ❌ No live Kubernetes API query |

---

#### UC-21 — View Infrastructure Metrics
| Field | Value |
|-------|-------|
| **Actor** | Platform Admin |
| **Trigger** | Navigate to Cluster Status page |
| **Main Flow** | Backend calls `GET /api/metrics` → returns CPU%, memory%, pod count, alert count |
| **Current state** | ❌ `/api/metrics` endpoint does not exist; frontend calls `/api/prometheus` with no query param which fails with 422 |
| **Gap** | ❌ API contract mismatch; ❌ No fallback to local psutil when Prometheus is unavailable |

---

#### UC-22 — Query Application Logs
| Field | Value |
|-------|-------|
| **Actor** | Platform Admin |
| **Trigger** | Navigate to Logs page, submit LogQL query |
| **Main Flow** | Frontend sends query → `/api/loki` proxies to Loki → results streamed to log panel |
| **Current state** | ✅ Endpoint implemented; ❌ returns error when LOKI_URL not set (currently empty) |

---

#### UC-30 — Stream Network Flows (OPNsense)
| Field | Value |
|-------|-------|
| **Actor** | OPNsense (automated) |
| **Trigger** | Flow collector polls pf state table every 2 seconds |
| **Main Flow** | 1. `pfctl -s states -v` via SSH → 2. Parse state table → 3. Extract 41 NSL-KDD features → 4. POST `/api/ingest` → 5. Inference → 6. WebSocket broadcast |
| **Current state** | ❌ Collector not implemented; `/api/ingest` endpoint does not exist |

---

## Gap Summary — Current vs Target

```mermaid
quadrantChart
    title Implementation Status vs Business Value
    x-axis Low Value --> High Value
    y-axis Not Implemented --> Implemented
    quadrant-1 Keep (done + valuable)
    quadrant-2 Build next (valuable, missing)
    quadrant-3 Defer (low value, missing)
    quadrant-4 Maintain (done, lower priority)

    UC-01 Live Feed: [0.85, 0.70]
    UC-04 Inject Attack: [0.60, 0.80]
    UC-03 Filter Alerts: [0.65, 0.55]
    UC-30 OPNsense Ingest: [0.95, 0.05]
    UC-21 Cluster Metrics: [0.70, 0.10]
    UC-10 Training Run: [0.85, 0.10]
    UC-13 Canary Rollout: [0.80, 0.15]
    UC-02 Flow Detail: [0.75, 0.05]
    UC-16 Drift Monitor: [0.70, 0.10]
    UC-05 Export History: [0.50, 0.05]
    UC-06 Acknowledge: [0.45, 0.05]
    UC-11 Version Compare: [0.65, 0.10]
```
