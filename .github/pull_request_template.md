## What & why

<!-- One or two sentences: what this change does and the reason for it. -->

## Service(s) touched

- [ ] inference
- [ ] collector
- [ ] backend-api
- [ ] aiops-engine
- [ ] frontend
- [ ] infra / CI / docs

## Checklist

- [ ] `ruff check .` passes for each touched service
- [ ] `pytest` passes for each touched service
- [ ] No secrets or hardcoded environment values added (config via env only)
- [ ] Docs updated if behaviour or the API surface changed
