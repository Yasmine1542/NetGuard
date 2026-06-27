# Deploying NetGuard to the cluster (run on the server)

Prereqs the manifests already encode: images pinned to `ghcr.io/yasmine1542/*`,
the ArgoCD Application points at this repo. Run everything below ON THE SERVER
(where `kubectl` targets the production cluster).

## 0. Make sure the images exist (do this first, from your dev box)
```bash
cd /home/master/netguard && git push        # pushes Batch-1 + the registry pins
```
Wait for the GitHub Actions run to go green → 5 images at
`ghcr.io/yasmine1542/netguard-{inference,collector,backend-api,aiops-engine,frontend}:latest`.

## 1. Pull the repo on the server
```bash
git clone https://github.com/Yasmine1542/NetGuard.git   # or: cd NetGuard && git pull
cd NetGuard
```

## 2. Namespace
```bash
kubectl apply -f k8s/00-namespace.yml
```

## 3. GHCR pull access (images are private by default)
Create a pull secret with a GitHub PAT that has `read:packages`:
```bash
kubectl -n netguard create secret docker-registry registry-secret \
  --docker-server=ghcr.io \
  --docker-username=Yasmine1542 \
  --docker-password='<PAT_with_read:packages>'
```
(Alternative: make the 5 GHCR packages **public** in GitHub → then no pull secret
is needed.)

## 4. App secrets
```bash
PW=$(openssl rand -hex 16)
kubectl -n netguard create secret generic netguard-secrets \
  --from-literal=GROQ_API_KEY='<your gsk_ key>' \
  --from-literal=POSTGRES_PASSWORD="$PW" \
  --from-literal=AIOPS_DB_URL="postgresql://aiops:${PW}@postgres:5432/aiops" \
  --from-literal=AIOPS_WEBHOOK_TOKEN="$(openssl rand -hex 16)"
```

## 5. Deploy
Direct (fast, for the first bring-up):
```bash
kubectl apply -f k8s/          # applies 00–30 (the rollouts/ subdir is intentionally excluded)
kubectl -n netguard get pods -w
```
Expect: redis + postgres first, then inference/collector/backend-api/aiops-engine,
then frontend. Postgres uses one Longhorn PVC; the rest are stateless.

GitOps alternative (the thesis path — same result, via Argo CD):
```bash
kubectl apply -f argocd/netguard-app.yml
argocd app sync netguard         # or the Argo CD UI
```

## 6. Access
```bash
kubectl -n netguard get ingress      # host: netguard.cluster.lan
```
Add `netguard.cluster.lan` → the MetalLB ingress VIP in your hosts file (or local
DNS), then open `https://netguard.cluster.lan`.

## 7. Progressive-delivery demo (optional, later)
See `k8s/rollouts/README.md` — scale up argo-rollouts, apply the Rollout + analysis,
push a new inference tag, watch the canary promote or auto-roll-back.

## Likely first hiccups
- `ImagePullBackOff` → packages still private / wrong PAT scope → fix the pull secret
  (or make packages public).
- aiops-engine `CreateContainerConfigError` → `netguard-secrets` missing a key.
- postgres `Pending` → Longhorn PVC not binding (check `kubectl -n netguard get pvc`
  and Longhorn health).
- 404 on the host → ingress not getting a VIP / hosts entry missing.
Paste any of these back and we'll fix it.
