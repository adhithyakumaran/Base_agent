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

### Login URL resolves without `/ea` (e.g. `.../tjdcom/login`)

Relative paths like `login` **replace** the last URL segment (`ea`) per browser URL rules.
Use `./login` or the absolute URL built from `EA_BASE_URL`:

```env
EA_BASE_URL=https://dev-ea.titanrts.com/ords/r/tjdcom/ea
EA_LOGIN_URL=login
```

Latest code uses absolute URLs for login setup automatically after `git pull`.

### Login setup fails (404 at `dev-ea.titanrts.com/login`)

Playwright treats paths starting with `/` as **domain-root** paths. With
`EA_BASE_URL=https://dev-ea.titanrts.com/ords/r/tjdcom/ea`, using `EA_LOGIN_URL=/login`
navigates to `https://dev-ea.titanrts.com/login` (404), not the app login page.

Use app-relative paths **without a leading slash**:

```env
EA_LOGIN_URL=login
EA_HOME_URL=home
```

(`/login` still works after `git pull` — the code strips the leading slash automatically.)

### Login setup fails (timeout on `#P9999_USERNAME`)

The UAT site uses **AppTrana WAF**, which blocks headless/automated Chromium (HTTP 406 — no login form). Normal Chrome works; bundled Playwright Chromium often does not.

1. In `automation/config/.env` set:
   ```env
   EA_HEADLESS=false
   EA_USE_SYSTEM_CHROME=true
   EA_BROWSER_CHANNEL=chrome
   ```
2. Confirm the full login URL opens in Chrome (not `dev-ea.titanrts.com/login` — that 404s):
   `https://dev-ea.titanrts.com/ords/r/tjdcom/ea/login`
3. Run headed debug (saves screenshot + HTML under `reports/`):
   ```bash
   npm run debug:login:headed
   ```
4. Retry: `npm run test:flow -- "@BF-LOGIN-001"`

## Enterprise standards

### Navigation rules (read before adding tests)

Oracle APEX friendly URLs live under `.../ords/r/tjdcom/ea/`. Playwright/browser URL rules cause subtle bugs:

| `.env` or `page.goto()` | Opens | Result |
|---|---|---|
| `EA_LOGIN_URL=/login` | `https://host/login` | 404 |
| `page.goto('login')` with base `.../ea` | `.../tjdcom/login` | drops `ea` |
| `page.goto('./login')` or `loginUrl()` | `.../tjdcom/ea/login` | correct |

**Always use helpers** from `src/fixtures/navigation.ts`:

- `gotoLogin(page)` / `loginUrl()` — auth entry
- `gotoApp(page, 'rivaah')` / `appPath()` — in-app routes with `./` prefix
- `gotoAppUrl(page, 'administration')` — absolute URL

`npm test` runs `scripts/validate-env.mjs` first and fails fast on bad `.env`.
Run `npm run test:unit-url` after URL helper changes.

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
