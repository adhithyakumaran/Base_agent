# Endless Aisle UAT — Enterprise Automation

Production-grade Playwright automation aligned with locked architecture (`docs/finalized-proposal/ARCHITECTURE_LOCKED.md`).

## Artifact hierarchy

```text
discovery/uat_ea/flows/          ← Approved KB (source of truth)
automation/test-design/flows/      ← Scenarios + test cases + per-flow suite (YAML)
automation/tests/                ← Playwright scripts (TypeScript)
automation/suites/               ← Sanity / regression suite manifests
automation/approval/             ← SME sign-off manifest
```

## Generate / refresh artifacts from KB

```bash
python3 scripts/generate_automation_artifacts.py
```

## Setup

```bash
cd automation
cp config/environments.example.env config/.env
# Edit .env with UAT URL and vault-backed credentials
npm install
npm run install:browsers
```

## Run

```bash
# Morning sanity (no LLM)
npm run test:sanity

# Full regression
npm run test:regression

# Single flow
npm run test:flow -- "@BF-LOGIN-001"
```

## Enterprise standards

| Standard | Implementation |
|---|---|
| Traceability | Test titles prefixed `TC-{flow_id}-*` |
| Locators | Primary + fallback chains from KB (`src/core/locator-chain.ts`) |
| Safety | Read-only guardrails for Admin / Manual Invoice / Reports |
| Evidence | Screenshot + URL attachment on failure |
| Secrets | Env vars only — never in KB or repo |
| SME gate | `approval/sme-manifest.yaml` must be APPROVED before prod CI |

## Orchestrator integration

```bash
QA_RUNNER=playwright QA_SUITE=sanity qa-orchestrator "run morning sanity"
```

See `src/qa_orchestrator/playwright_runner.py`.
