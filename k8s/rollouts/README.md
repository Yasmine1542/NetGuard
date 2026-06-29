# Inference canary (Argo Rollouts) — now part of GitOps

The canary is no longer a manual side-demo. The Rollout, its AnalysisTemplate and
the ServiceMonitor moved into the top-level `k8s/` tree and are deployed by the
`netguard` ArgoCD Application (see `argocd/apps/netguard.yml`):

- `k8s/20-inference.yml` — the inference **Rollout** (canary strategy) + Service
- `k8s/25-inference-analysis.yml` — the `inference-health` AnalysisTemplate (gate)
- `k8s/26-inference-servicemonitor.yml` — scrape config feeding the gate

Prerequisite: the argo-rollouts controller (ansible `playbooks/30-argo-rollouts.yml`).

## Demo a model update + canary
```bash
# A new model = a new image tag. Trigger the canary by bumping the tag:
kubectl argo rollouts -n netguard set image inference \
  inference=ghcr.io/yasmine1542/netguard-inference:<new-tag>
kubectl argo rollouts -n netguard get rollout inference --watch
```
- Healthy new version → 50% → analysis passes → promoted to 100%.
- Bad version (model fails to load / latency spikes) → analysis fails → automatic
  rollback to the previous stable ReplicaSet. Capture this for the report.

Note: with the image pinned to a moving `:latest` tag, a registry push alone does
NOT retrigger the canary (the Rollout pod template is unchanged). Trigger it with
`set image` to an immutable tag, or wire Argo CD Image Updater to bump the tag in
git automatically (tracked under the Azure/CD task).
