# Azure Key Vault + External Secrets Operator

Goal: move the cluster's application secrets (Groq API key, AIOps DB URL) out of a
manually-created Kubernetes Secret and into Azure Key Vault, synced into the cluster by
the External Secrets Operator (ESO). ESO becomes the source of the `netguard-secrets`
Secret that `aiops-engine` consumes.

Because the cluster is on-premises (not on Azure), ESO authenticates to Key Vault with a
**Service Principal** (App Registration + client secret). Managed Identity is not
available off-Azure.

> ⚠️ Gate: creating the App Registration / client secret may be blocked by the tenant's
> Conditional Access policy (the same class of policy that blocked `az login`). Do
> **Portal step 3 first** — if it fails, this approach is deferred and the manual
> `netguard-secrets` Secret stays in place.

## Portal (Azure)

1. **Create the Key Vault.** Create resource → Key Vault, name `netguard-kv` (or similar),
   same region/resource group as the ACR. Permission model: **Azure RBAC**.
2. **Add the secrets.** Key Vault → Secrets → Generate/Import:
   - `groq-api-key`  = the Groq API key
   - `aiops-db-url`  = the Postgres URL aiops-engine uses (`postgresql://...`)
3. **Create the Service Principal.** Microsoft Entra ID → App registrations → New
   registration (`netguard-eso`). Note the **Application (client) ID** and **Directory
   (tenant) ID**. Then Certificates & secrets → New client secret → copy the **value**.
   *(If this step is blocked by policy, stop here.)*
4. **Grant the SP read access to the vault.** Key Vault → Access control (IAM) → Add role
   assignment → **Key Vault Secrets User** → assign to `netguard-eso`.

## Cluster

```bash
# 1. Bootstrap secret with the SP credentials (never committed to Git)
kubectl -n netguard create secret generic azure-kv-creds \
  --from-literal=client-id='<application-client-id>' \
  --from-literal=client-secret='<client-secret-value>'

# 2. Install the External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
helm upgrade --install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace --set installCRDs=true --wait

# 3. Fill <your-vault-name> and <your-tenant-id> in cluster-secret-store.yaml, then:
kubectl apply -f k8s/external-secrets/cluster-secret-store.yaml
kubectl apply -f k8s/external-secrets/external-secret-netguard.yaml

# 4. Verify — ESO should recreate netguard-secrets from Key Vault
kubectl -n netguard get externalsecret netguard-secrets   # STATUS: SecretSynced
kubectl -n netguard get secret netguard-secrets -o jsonpath='{.data.GROQ_API_KEY}' | base64 -d | head -c4
kubectl -n netguard rollout restart deploy/aiops-engine    # pick up the synced Secret
```

## Evidence for the report
- Key Vault Secrets blade showing `groq-api-key` / `aiops-db-url`.
- `kubectl get externalsecret` showing `SecretSynced` / `Ready=True`.
- The `netguard-secrets` Secret now `Owned` by ESO (not manual).
