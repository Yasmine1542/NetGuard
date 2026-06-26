# Inference canary (Argo Rollouts)

Progressive delivery for the `inference` service, kept separate from the base
deployment so the platform runs fine without argo-rollouts and the canary is a
deliberate demo. The canary shifts traffic in steps and is gated by a Prometheus
`AnalysisTemplate`; if the gate fails it auto-rolls-back to the stable version.

## One-time prerequisites
```bash
# argo-rollouts controller must be running (we scaled it to 0 during cleanup):
kubectl -n argo-rollouts scale deploy argo-rollouts --replicas=1

# scrape config + gate
kubectl apply -f inference-servicemonitor.yml
kubectl apply -f inference-analysis.yml
```

## Switch inference to the Rollout (supersedes the Deployment)
```bash
kubectl -n netguard scale deploy inference --replicas=0   # or: kubectl -n netguard delete deploy inference
kubectl apply -f inference-rollout.yml
kubectl argo rollouts -n netguard get rollout inference --watch
```

## Demo a model update + canary
```bash
# point the rollout at a new image tag (a retrained model)
kubectl argo rollouts -n netguard set image inference \
  inference=<acr>/netguard-inference:<new-tag>
kubectl argo rollouts -n netguard get rollout inference --watch
```
- Healthy new version → 50% → analysis passes → promoted to 100%.
- Bad version (model fails to load / latency spikes) → analysis fails → automatic
  rollback to the previous stable ReplicaSet. Capture this for the report.
