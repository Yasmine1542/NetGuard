# Free pipeline test path (GHCR)

Validate the full CI pipeline (lint -> test -> build -> Trivy -> push) for **$0**:
Azure DevOps public project + Microsoft-hosted agents (free) pushing to **GitHub
Container Registry** (free). The pipeline YAML is registry-agnostic, so switching
to ACR later is just a variable-group change — no YAML edits.

## 1. Azure DevOps org + public project
- Create a free org at https://dev.azure.com.
- New project **NetGuard**, Visibility = **Public** (free Microsoft-hosted minutes,
  no parallelism-grant wait).

## 2. GitHub token for GHCR
Create a GitHub **Personal Access Token (classic)** with scopes:
`write:packages`, `read:packages` (and `repo` only if the source repo were private).

## 3. GHCR service connection (Azure DevOps → Project Settings → Service connections)
- New → **Docker Registry** → Registry type **Others**
- Docker Registry URL: `https://ghcr.io`
- Docker ID: `yasmine1542`
- Password: the PAT from step 2
- Name: `ghcr-conn`  → Save

## 4. GitHub service connection
First time you create a pipeline from the GitHub repo, Azure DevOps prompts to
install the **Azure Pipelines** GitHub App on `Yasmine1542/NetGuard` — authorize it.

## 5. Variable group `netguard-registry`
Pipelines → Library → + Variable group, name **netguard-registry**:

| Variable | Value |
|---|---|
| `registryConnection` | `ghcr-conn` |
| `registryHost` | `ghcr.io` |
| `imageRepoPrefix` | `yasmine1542/netguard-`  (must be lowercase) |

(For the ACR version later, the same group becomes: `registryConnection=<acr-conn>`,
`registryHost=<acr>.azurecr.io`, `imageRepoPrefix=netguard-`.)

## 6. Create the pipelines
Pipelines → New pipeline → **GitHub** → `Yasmine1542/NetGuard` →
**Existing Azure Pipelines YAML file** → pick `/azure-pipelines/inference.yml` →
Save. Repeat for `collector.yml`, `backend-api.yml`, `aiops-engine.yml`,
`frontend.yml`.

## 7. Run
Run the inference pipeline first. Green = lint+test passed, image built, Trivy
found no HIGH/CRITICAL, and the image is in GHCR at
`ghcr.io/yasmine1542/netguard-inference`. Check it under your GitHub profile →
Packages. (Packages are private by default; make them public or add a pull
secret when deploying.)
