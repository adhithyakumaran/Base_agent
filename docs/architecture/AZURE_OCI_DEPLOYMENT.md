# Deployment sketch — Azure Pipelines → OCI

## Model

- **Azure Repos + Azure Pipelines**: CI/CD (build, test, package, deploy). Not the runtime host.  
- **OCI (client)**: runtime for Base Agent / QA services when required for residency.  
- **Artifacts**: versioned container images (preferred over shipping raw source into client admin hands).

## Pipeline stages (target)

1. `lint` + `pytest` (deterministic suite, `LLM_ENABLED=false`)  
2. Package image (`base-agent:<semver>`)  
3. Push to OCI registry / client-approved registry  
4. Deploy via OCI Container Instances / OKE / VM + systemd (client choice)  
5. Config via secrets: `TARGET_URL`, credentials, model gateway endpoint, budgets

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
