# Oracle APEX crawler & QA skill notes (enterprise)

## APEX realities that break naive crawlers

1. **Session in URL** — friendly URLs need current `session=` on explicit `goto`; prefer click navigation.  
2. **AJAX / `wwv_flow.ajax`** — LOVs, IGs, cards often complete async; wait on ajax or DOM settle, not infinite `networkidle` only.  
3. **Modals / drawers / dialogs** — Customer select, settings, size variants; dedicated modal timeout, never block the crawl budget.  
4. **Multi-app surface** — Endless Aisle uses `ea`, `ea1`, sometimes `gc` and other apps under same workspace.  
5. **CSP / typed login** — some pages need real keystrokes (`type`) not only `fill`.  
6. **Selector strategy** — prefer APEX static IDs / item names (`#P6_SKU`) over long CSS chains; keep locator map in KB components.

## Anti-stuck policy (mandatory)

| Guard | Default |
|---|---|
| `max_pages` | 40 / run |
| Same URL visit | 1 (unless explicit re-enter) |
| Modal wait | 3s then dismiss/skip |
| Navigation timeout | 45s |
| Per-page settle | 1–2s + ajax wait when detected |
| External host | skip |
| Separator / landing ORDS | skip + record blocker |
| Budget on pages | Decision Engine stops crawl |

## Skill split

- `qa.apex.discover` — KB snapshot and/or live `ApexCrawler` (`plugins/qa_apex/crawler/`)  
- `qa.apex.sanity_probe` — deterministic technical rules + KB presence (no business GT)  
- `qa.apex.flow_catalog` — candidate product flows + platform `flow_pattern` docs  
- Future: dedicated browser plugin, API plugin, evidence plugin  

Base Agent stays framework; APEX specifics stay in `plugins/qa_apex`.

See also: [APEX_APPLICATION_FLOWS.md](APEX_APPLICATION_FLOWS.md).

## Efficiency

- Reuse KB between runs (diff by `content_hash`)  
- Do not re-crawl unchanged aliases (`normalize_page_key` strips session/cs)  
- Modal dismiss within `modal_timeout_ms` then continue  
- Bounded ajax wait (`jquery.active` / timeout) — never hang on `networkidle` alone  
- Parallel only for `parallel_safe` reads  
- LLM not involved in crawl loop  
- Live failure degrades to KB snapshot so the agent still returns useful structure
