# CI/CD & Azure runbook

End-to-end: provision the minimal Azure footprint (ACR + Azure Pipelines, plus
optional Blob Storage), wire CI to push images, and deliver to the on-prem
cluster via ArgoCD. Hybrid model: **cloud CI → on-prem GitOps CD**.

Assumes the clean NetGuard repo has `demo-app/` as its root (so paths are
`services/…`, `k8s/…`). If you deploy from the monorepo instead, prefix paths
with `demo-app/`.

## 0. Variables
```bash
RG=netguard-rg; LOC=francecentral; ACR=netguardacr
```

## 1. Azure Container Registry
```bash
az group create -n $RG -l $LOC
az acr create -n $ACR -g $RG --sku Basic --admin-enabled true
ACR_LOGIN=$(az acr show -n $ACR --query loginServer -o tsv); echo "$ACR_LOGIN"
```

## 2. (Optional) Azure Blob Storage — model / incident archive
```bash
az storage account create -n netguardsa -g $RG -l $LOC --sku Standard_LRS
az storage container create --account-name netguardsa -n models
az storage container create --account-name netguardsa -n incidents
```

## 3. Azure DevOps: pipelines → ACR
```bash
az extension add --name azure-devops
az devops configure --defaults organization=https://dev.azure.com/<org> project=NetGuard
```
- In the project, create a **Docker Registry service connection** to the ACR
  (Project settings → Service connections). Name it e.g. `netguard-acr-conn`.
- Create the variable group the pipelines reference:
```bash
az pipelines variable-group create --name netguard-acr \
  --variables acrName=$ACR_LOGIN acrServiceConnection=netguard-acr-conn
```
- Create one pipeline per service from its YAML (repeat for collector,
  backend-api, aiops-engine, frontend):
```bash
az pipelines create --name netguard-inference \
  --repository <repo> --repository-type github --branch main \
  --yml-path azure-pipelines/inference.yml --skip-first-run true
```
Each pipeline runs on Microsoft-hosted `ubuntu-latest`. To use a self-hosted
agent (e.g. to keep builds on your network), create an agent pool and replace
`pool: { vmImage: ubuntu-latest }` with `pool: { name: <your-pool> }`.

## 4. Point the manifests + ArgoCD at the real registry/repo
```bash
# bake the ACR login server into the k8s manifests + rollout
grep -rl REGISTRY_PLACEHOLDER k8s | xargs sed -i "s#REGISTRY_PLACEHOLDER#$ACR_LOGIN#g"
# set the git repo in the ArgoCD Application
sed -i "s#REPO_URL_PLACEHOLDER#https://github.com/<you>/netguard.git#g" argocd/netguard-app.yml
git add -A && git commit -m "chore: pin ACR + repo URL" && git push
```

## 5. Cluster pull secret (so ArgoCD-deployed pods can pull from ACR)
```bash
ACR_USER=$(az acr credential show -n $ACR --query username -o tsv)
ACR_PASS=$(az acr credential show -n $ACR --query 'passwords[0].value' -o tsv)
kubectl create namespace netguard --dry-run=client -o yaml | kubectl apply -f -
kubectl -n netguard create secret docker-registry registry-secret \
  --docker-server=$ACR_LOGIN --docker-username=$ACR_USER --docker-password=$ACR_PASS
```

## 6. App secret (Groq + Postgres)
```bash
kubectl -n netguard create secret generic netguard-secrets \
  --from-literal=GROQ_API_KEY='gsk_...' \
  --from-literal=POSTGRES_PASSWORD='<pw>' \
  --from-literal=AIOPS_DB_URL='postgresql://aiops:<pw>@postgres:5432/aiops'
```

## 7. Deliver via ArgoCD (GitOps CD)
```bash
kubectl apply -f argocd/netguard-app.yml
argocd app sync netguard        # or the ArgoCD UI
kubectl -n netguard get pods
```
Add `netguard.cluster.lan` → MetalLB VIP to your hosts file, then open
`https://netguard.cluster.lan`.

## 8. Progressive delivery demo (canary)
See `k8s/rollouts/README.md` — scale up argo-rollouts, apply the Rollout, push a
new inference tag, and watch the analysis promote or auto-roll-back.
