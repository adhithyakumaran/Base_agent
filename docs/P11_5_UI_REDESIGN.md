# P11.5 — ScoutAI UI/UX redesign (presentation only)

Visual refresh to a light enterprise SaaS language (Composio-inspired hierarchy, not copied branding).

## Scope

**Changed:** design tokens, typography, layout, spacing, copy on primary surfaces, component styling.

**Unchanged:** APIs, orchestration, run behavior, auth, SSE, approvals, reporting logic, data models.

## Design system

Tokens live in `apps/console/styles/design-tokens.css`:

- `--background`, `--surface`, `--surface-muted`, `--text-primary`, `--text-secondary`, `--border`, `--accent`, `--accent-soft`, `--success`, `--warning`, `--danger`
- Subtle `--gradient-hero` / `--gradient-accent` for Ask Agent command card only
- Light theme enforced (`color-scheme: light`)

Typography (`app/layout.tsx`):

- **Inter** — UI body
- **Space Grotesk** — display headings
- **IBM Plex Mono** — technical values

## Key surfaces

| Surface | Notes |
| --- | --- |
| Sidebar | White, subtle border, light blue active state, same nav groups |
| Top bar | Typography + separators instead of pill cluster |
| Ask Agent | Hero copy, gradient command card, Run readiness card, Latest run |
| Runs | Timeline cards, collapsible activity log, export unchanged |
| Evidence | Screenshot grid + preview |
| Flows / Approvals | Cleaner headers, same tables and actions |

## Validation

```bash
cd apps/console && npm run typecheck && npm run lint && npm run build
```

Manual: verify Ask Agent run, run detail, exports, approvals, flows, evidence, live polling.
