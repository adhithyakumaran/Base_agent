# Deployment sketch — Azure Pipelines → OCI

## Model

- **Azure Repos + Azure Pipelines**: CI/CD (build, test, package, deploy). Not the runtime host.  
- **OCI (client)**: runtime for Base Agent / QA services when required for residency.  
- **Artifacts**: versioned container images (preferred over shipping raw source into client admin hands).

## Pipeline stages (target)

Implemented skeleton: [`azure-pipelines.yml`](../../azure-pipelines.yml) + [`deploy/Dockerfile`](../../deploy/Dockerfile).

1. `pytest` unit suite (`LLM_ENABLED=false`) + CLI smoke on KB  
2. Package image (`base-agent:<BuildId>`)  
3. Push to OCI registry / client-approved registry (wire service connection)  
4. Deploy via OCI Container Instances / OKE / VM + systemd (manual gate `DeployOCI=true`)  
5. Config via secrets: `APEX_TARGET_URL` / `TARGET_URL`, credentials, `LLM_*` gateway models, budgets

## Enterprise LLM

- Behind `LlmGateway` only (LiteLLM/Router or client gateway)  
- Roles: fast / reasoning / fallback  
- Default **off** for crawl/sanity deterministic paths  
- Token + cost counters on every call  
- No vendor SDK imports inside Decision Engine / executor

## Security

- Secrets in Azure Key Vault / OCI Vault — never in git  
- Redact cookies/passwords in traces  
- Tool output is untrusted data (prompt-injection safe)  
- Plugin permission manifests enforced before execute

## IP note

Container on client OCI is **not** perfect source secrecy. Prefer packaged artifact + contracts; confirm client admin access model.
