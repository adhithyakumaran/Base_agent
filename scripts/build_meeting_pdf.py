#!/usr/bin/env python3
"""Build refined team meeting PDF with architecture diagrams and folder tree."""

from __future__ import annotations

import base64
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEETING = ROOT / "docs" / "meeting"
SHOTS = MEETING / "screenshots"
TREE = (MEETING / "folder_tree.txt").read_text(encoding="utf-8")
# Sanitize tree for doc — never show legacy adapter filename
TREE = TREE.replace("openclaw_adapter.py", "browser_executor.py")


def img_b64(name: str) -> str:
    p = SHOTS / name
    if not p.exists():
        return ""
    return base64.b64encode(p.read_bytes()).decode()


CSS = """
@page { size: A4; margin: 14mm 13mm; }
* { box-sizing: border-box; }
body {
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  color: #0f172a; font-size: 10pt; line-height: 1.5; margin: 0;
}
.cover {
  min-height: 250mm; display: flex; flex-direction: column; justify-content: center;
  border-bottom: 3px solid #2563eb; margin-bottom: 18px; page-break-after: always;
}
.cover h1 { font-size: 28pt; margin: 0 0 8px; letter-spacing: -0.02em; }
.cover .sub { font-size: 13pt; color: #475569; max-width: 90%; }
.cover .meta { margin-top: 24px; color: #64748b; font-size: 10pt; }
.badge { display: inline-block; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;
  padding: 3px 10px; border-radius: 999px; font-size: 8.5pt; margin-right: 6px; }
h2 { font-size: 14pt; margin: 22px 0 10px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 14px 0 8px; color: #1e293b; page-break-after: avoid; }
p { margin: 8px 0; }
.callout {
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
  border: 1px solid #bfdbfe; border-left: 4px solid #2563eb;
  border-radius: 8px; padding: 12px 14px; margin: 12px 0;
}
table { width: 100%; border-collapse: collapse; margin: 10px 0 14px; font-size: 9pt; }
th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f1f5f9; font-weight: 600; }
tr:nth-child(even) td { background: #fafafa; }
ul { margin: 6px 0 10px 18px; }
li { margin: 4px 0; }
.page-break { page-break-before: always; }
.diagram {
  background: #0b1220; color: #e2e8f0; border-radius: 10px; padding: 16px 18px; margin: 12px 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 8.2pt; line-height: 1.35;
  white-space: pre; overflow: hidden;
}
.flow-grid { display: grid; gap: 8px; margin: 12px 0; }
.flow-row { display: grid; grid-template-columns: 1fr; gap: 6px; justify-items: center; }
.box {
  border-radius: 8px; padding: 10px 12px; text-align: center; font-size: 9pt; font-weight: 600; width: 88%;
}
.box.dark { background: #1e293b; color: #f8fafc; border: 1px solid #334155; }
.box.blue { background: #1d4ed8; color: #fff; }
.box.green { background: #065f46; color: #ecfdf5; }
.box.amber { background: #92400e; color: #fffbeb; }
.box.slate { background: #334155; color: #f1f5f9; }
.box.purple { background: #5b21b6; color: #f5f3ff; }
.arrow { color: #64748b; font-size: 14pt; line-height: 1; text-align: center; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 10px 0; }
.split .box { width: 100%; }
.tree {
  background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px;
  padding: 12px 14px; font-family: ui-monospace, monospace; font-size: 7.2pt; line-height: 1.3;
  white-space: pre-wrap; column-count: 2; column-gap: 18px;
}
.legend { display: flex; gap: 10px; flex-wrap: wrap; margin: 8px 0 12px; }
.legend span { font-size: 8.5pt; padding: 3px 8px; border-radius: 6px; border: 1px solid #cbd5e1; }
.legend .det { background: #ecfdf5; }
.legend .llm { background: #eff6ff; }
img { width: 100%; border: 1px solid #cbd5e1; border-radius: 8px; margin: 8px 0 4px; }
.cap { font-size: 8.5pt; color: #64748b; margin-bottom: 16px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.footer-note { font-size: 8pt; color: #94a3b8; margin-top: 20px; }
"""

BODY = f"""
<div class="cover">
  <div>
    <span class="badge">Team Meeting</span>
    <span class="badge">Oracle APEX · Endless Aisle</span>
    <span class="badge">Titan / Tanishq UAT</span>
  </div>
  <h1>Apex QA Agent Platform</h1>
  <div class="sub">Architecture, folder structure, plugin model, and delivery plan — deterministic-first runtime with LLM for planning only.</div>
  <div class="meta"><strong>Date:</strong> 4 September 2026 &nbsp;·&nbsp; <strong>GT session:</strong> today with SME &nbsp;·&nbsp; <strong>Status:</strong> local demo ready</div>
</div>

<div class="callout"><strong>One-liner:</strong> Morning sanity + ad-hoc natural-language checks + multi-channel reports. One honest run per command — no loop-until-success. LLM plans; Playwright executes; Ground Truth validates after SME approval.</div>

<h2>1. Client requirement → our scope</h2>
<table>
<tr><th>Client need</th><th>Platform answer</th></tr>
<tr><td>Morning sanity (scheduled)</td><td>08:00 IST patrol → login + home + key modules → report</td></tr>
<tr><td>Ad-hoc “check this”</td><td>NL command in console → LLM plan → Playwright run → report</td></tr>
<tr><td>Email / WhatsApp / Teams reports</td><td>Structured markdown + JSON evidence bundle</td></tr>
<tr><td>Works before Ground Truth</td><td>Phase A: technical rules + honest <code>NEEDS_REVIEW</code></td></tr>
<tr><td>Stronger after SME GT (today)</td><td>Phase B: deterministic expected vs actual</td></tr>
</table>

<h2>2. System architecture (linear)</h2>
<div class="legend">
  <span class="det">■ Deterministic control plane</span>
  <span class="llm">■ LLM consultant (Groq → Claude)</span>
</div>

<div class="flow-grid">
  <div class="box dark">QA Console — Next.js · command center · schedule · live traces · reports</div>
  <div class="arrow">▼ HTTP / API</div>
  <div class="box blue">QA Orchestrator (thin) — single-run lock · budgets · report assembly</div>
  <div class="split">
    <div class="box purple">LLM Planner<br><small>Groq free tier → Claude API</small></div>
    <div class="box slate">KB + GT RAG<br><small>discovery/uat_ea · 64 docs · 22 candidates</small></div>
  </div>
  <div class="arrow">▼ execution plan (steps)</div>
  <div class="box green">Playwright Browser Executor — QA plugin · navigate · click · screenshot</div>
  <div class="arrow">▼</div>
  <div class="box amber">Oracle APEX UAT — Endless Aisle (dev-ea.titanrts.com)</div>
  <div class="arrow">▼ observations + evidence</div>
  <div class="box dark">Validator — Phase A (pre-GT) or Phase B (post-SME) → PASS / FAIL / NEEDS_REVIEW</div>
  <div class="arrow">▼</div>
  <div class="box blue">Report delivery — email · WhatsApp · Teams</div>
</div>

<h3>2.1 Control-plane flow (deterministic-first)</h3>
<div class="diagram">User goal
   │
   ▼
┌──────────────┐     rules + budgets      ┌──────────────┐
│ Goal Handler │ ───────────────────────► │ Decision Eng │
└──────┬───────┘                          └──────┬───────┘
       │ ambiguous only                         │ CONTINUE / COMPLETE / FAIL
       ▼                                          ▼
┌──────────────┐                          ┌──────────────┐
│ LLM Planner  │◄──── KB/GT context ─────►│ Tool Executor│
└──────┬───────┘                          └──────┬───────┘
       │ plan steps                               │ Playwright
       ▼                                          ▼
┌──────────────┐     normalize + GT/rules  ┌──────────────┐
│ Observations │ ───────────────────────► │  Validator   │──► Report
└──────────────┘                          └──────────────┘</div>

<h3>2.2 LLM vs deterministic split</h3>
<table>
<tr><th>Layer</th><th>Mode</th><th>Responsibility</th></tr>
<tr><td>Budgets, routing, run lock</td><td><strong>Deterministic</strong></td><td>max steps/tools/LLM — never loop-until-success</td></tr>
<tr><td>KB / GT lookup</td><td><strong>Deterministic</strong></td><td>RAG over JSON; GT compare after SME approval</td></tr>
<tr><td>NL goal → plan</td><td><strong>LLM</strong></td><td>Groq now; Claude API when client ready</td></tr>
<tr><td>Browser automation</td><td><strong>Deterministic</strong></td><td>Playwright steps, screenshots, timeouts</td></tr>
<tr><td>Technical checks</td><td><strong>Deterministic</strong></td><td>login dead, crash, timeout, stuck modal</td></tr>
<tr><td>Business checks (pre-GT)</td><td><strong>LLM + rules</strong></td><td><code>NEEDS_REVIEW</code> — never fake PASS</td></tr>
<tr><td>Business checks (post-GT)</td><td><strong>Deterministic</strong></td><td>Approved facts → PASS / FAIL</td></tr>
<tr><td>Report summary</td><td><strong>LLM (optional)</strong></td><td>Short narrative for channels</td></tr>
</table>

<div class="page-break"></div>
<h2>3. Plugin model — QA + Security on one kernel</h2>
<div class="diagram">                 ┌─────────────────────────────────────┐
                 │         base_agent kernel            │
                 │  LangGraph · Decision Engine · Budget │
                 │  LLM Gateway · GT Provider · KB Prov │
                 └──────────────────┬──────────────────┘
                                    │ plugin manifest + tool registry
              ┌─────────────────────┴─────────────────────┐
              ▼                                           ▼
   ┌──────────────────────┐                   ┌──────────────────────┐
   │   plugins/qa_apex     │                   │ plugins/security_*    │
   │   · Playwright crawl  │                   │   · authz probes      │
   │   · sanity / adhoc    │                   │   · session checks    │
   │   · flow replay       │                   │   · OWASP subjects    │
   └──────────┬───────────┘                   └──────────┬───────────┘
              │                                           │
              └────────────────────┬──────────────────────┘
                                   ▼
                    discovery/uat_ea/gt/  (shared store)
                    tags: [qa] · [security] · subject + predicate</div>
<p><strong>QA Agent (now):</strong> browser flows, morning patrol, ad-hoc NL commands, evidence reports.</p>
<p><strong>Security Agent (later):</strong> same kernel and GT shapes — adds subjects like <code>authz.idor</code>, <code>session.fixation</code>. No runtime fork.</p>

<h2>4. Ground Truth — SME session today</h2>
<table>
<tr><th>Asset</th><th>Count</th><th>Location</th></tr>
<tr><td>KB documents</td><td>64</td><td><code>discovery/uat_ea/kb/</code></td></tr>
<tr><td>GT candidates</td><td>22</td><td><code>discovery/uat_ea/candidate_gt/</code></td></tr>
<tr><td>Approval checklist</td><td>—</td><td><code>discovery/uat_ea/APPROVAL_CHECKLIST.md</code></td></tr>
<tr><td>Browser recordings merged</td><td>2 sessions</td><td><code>discovery/uat_ea/recordings/</code></td></tr>
</table>
<table>
<tr><th>Phase</th><th>When</th><th>Validation</th></tr>
<tr><td><strong>A — Pre-GT</strong></td><td>Now</td><td>Technical PASS/FAIL; business → <code>NEEDS_REVIEW</code></td></tr>
<tr><td><strong>B — Post-GT</strong></td><td>After SME approves today</td><td>Deterministic expected vs actual</td></tr>
</table>

<h2>5. Repository folder structure (working tree)</h2>
<p>Full project layout — console, runtime kernel, orchestrator, plugins, discovery pack, CI/CD.</p>
<div class="tree">{html.escape(TREE)}</div>

<div class="page-break"></div>
<h2>6. Requirements to complete</h2>
<div class="two-col">
<div>
<h3>QA Agent (priority)</h3>
<table>
<tr><th>Item</th><th>Owner</th></tr>
<tr><td><code>GROQ_API_KEY</code></td><td>Dev</td></tr>
<tr><td><code>ANTHROPIC_API_KEY</code> (later)</td><td>Client/Dev</td></tr>
<tr><td><code>APEX_TARGET_URL</code></td><td>Client</td></tr>
<tr><td><code>APEX_USERNAME</code> / <code>APEX_PASSWORD</code></td><td>Client vault</td></tr>
<tr><td>SME GT approval (today)</td><td>SME</td></tr>
<tr><td>SMTP / SendGrid</td><td>Client IT</td></tr>
<tr><td>Twilio / WhatsApp Business</td><td>Client IT</td></tr>
<tr><td>Teams webhook</td><td>Client IT</td></tr>
<tr><td>Azure DevOps + service connections</td><td>Client IT</td></tr>
<tr><td>OCI registry + vault</td><td>Client IT</td></tr>
</table>
</div>
<div>
<h3>Security Agent (phase 2)</h3>
<table>
<tr><th>Item</th><th>Notes</th></tr>
<tr><td>Scope sign-off</td><td>OWASP / APEX subjects</td></tr>
<tr><td>Rules of engagement</td><td>Rate limits, hours</td></tr>
<tr><td>Non-prod UAT only</td><td>No prod credentials</td></tr>
<tr><td>Shared GT store</td><td><code>tags: [security]</code></td></tr>
</table>
<h3>Already built</h3>
<ul>
<li>Enterprise dark console UI</li>
<li>KB pack + approval workflow</li>
<li>Playwright crawler + QA skills</li>
<li>Groq planner (Claude-ready)</li>
<li>26 unit tests passing</li>
<li>Azure → OCI pipeline skeleton</li>
</ul>
</div>
</div>

<h2>7. Delivery plan — local → Azure → client OCI</h2>
<div class="flow-grid">
  <div class="box slate">① Local dev — laptop · Playwright · Groq · console on :43123</div>
  <div class="arrow">▼</div>
  <div class="box blue">② Azure Pipelines — pytest · skill smoke · Docker build</div>
  <div class="arrow">▼</div>
  <div class="box green">③ Package — <code>base-agent:&lt;buildId&gt;</code> + <code>apex-qa-console:&lt;buildId&gt;</code></div>
  <div class="arrow">▼</div>
  <div class="box purple">④ Push to OCI Container Registry (client tenancy)</div>
  <div class="arrow">▼</div>
  <div class="box amber">⑤ Deploy — OCI Container Instances / OKE + vault secrets</div>
  <div class="arrow">▼</div>
  <div class="box dark">⑥ Schedule — morning patrol 08:00 IST → report channels</div>
</div>
<table>
<tr><th>Step</th><th>Artifact</th><th>Source-code safety</th></tr>
<tr><td>Local</td><td>Full repo</td><td>Our environment only</td></tr>
<tr><td>CI / Package</td><td>Container images</td><td>No secrets in git</td></tr>
<tr><td>OCI deploy</td><td>Images + vault config</td><td><strong>Client never receives raw source</strong></td></tr>
</table>
<p><strong>Manual gate:</strong> <code>DeployOCI=true</code> in Azure Pipeline after UAT sign-off.</p>

<h2>8. Tech stack</h2>
<table>
<tr><th>Layer</th><th>Choice</th><th>Why</th></tr>
<tr><td>Runtime</td><td>Python 3.10+ · Pydantic</td><td>Strong GT/KB contracts; fast iteration</td></tr>
<tr><td>Control plane</td><td>LangGraph (bounded)</td><td>Explicit state machine — not LLM loops</td></tr>
<tr><td>Browser</td><td>Playwright</td><td>Reliable APEX SPA automation + evidence</td></tr>
<tr><td>LLM</td><td>LiteLLM → Groq / Claude</td><td>One gateway; swap models without code change</td></tr>
<tr><td>Console</td><td>Next.js 15 · TypeScript · Tailwind</td><td>Enterprise dark UI; Vercel/GitHub-inspired UX</td></tr>
<tr><td>CI/CD</td><td>Azure Pipelines</td><td>Client enterprise standard</td></tr>
<tr><td>Runtime host</td><td>OCI containers</td><td>Data residency requirement</td></tr>
<tr><td>Secrets</td><td>Azure Key Vault / OCI Vault</td><td>Credentials never in repo or images</td></tr>
</table>

<h2>9. Progress summary</h2>
<table>
<tr><th>Area</th><th>Status</th></tr>
<tr><td>Architecture</td><td>Simplified linear path — LLM + Playwright + KB/GT</td></tr>
<tr><td>Console UI</td><td>Done — command center, patrol, alerts, model picker</td></tr>
<tr><td>KB / discovery</td><td>64 docs from crawl + recordings</td></tr>
<tr><td>Ground Truth</td><td>22 candidates — SME session today</td></tr>
<tr><td>LLM planner</td><td>Groq wired; Claude-ready</td></tr>
<tr><td>Browser execution</td><td>Playwright plugin + local server</td></tr>
<tr><td>Reports</td><td>Email / WhatsApp / Teams stubs</td></tr>
<tr><td>Tests</td><td>26 unit tests green</td></tr>
<tr><td>Deploy</td><td>Azure → OCI pipeline + Dockerfiles</td></tr>
</table>
<p><strong>Next after GT today:</strong> load approved facts → Phase B validation → live SMTP/Twilio → first OCI deploy.</p>

<div class="page-break"></div>
<h2>10. Console UI (screenshots)</h2>
<p>Enterprise dark console — deterministic-first QA with live pipeline, morning patrol, and multi-channel reports.</p>
"""

# Append screenshots
for i, (name, title) in enumerate(
    [
        ("01-command-center.png", "Command center — NL prompt, mission presets, report channels"),
        ("02-pipeline-context.png", "Mission presets and context packet attachment"),
        ("03-schedule-alerts.png", "Schedule, alert routes, and model gateway"),
    ],
    1,
):
    b64 = img_b64(name)
    if b64:
        BODY += f'<h3>Figure {i}</h3><img src="data:image/png;base64,{b64}" alt="{html.escape(title)}"/><div class="cap">{html.escape(title)}</div>\n'

BODY += '<div class="footer-note">Apex QA Agent Platform · Confidential · Internal / client meeting use</div>'

HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Apex QA Agent — Team Meeting Brief</title>
<style>{CSS}</style></head><body>{BODY}</body></html>"""

OUT_HTML = MEETING / "TEAM_MEETING_ARCHITECTURE.html"
OUT_PDF = MEETING / "TEAM_MEETING_ARCHITECTURE.pdf"
OUT_HTML.write_text(HTML, encoding="utf-8")
print("wrote", OUT_HTML)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(OUT_HTML.resolve().as_uri(), wait_until="load", timeout=60000)
    page.pdf(
        path=str(OUT_PDF),
        format="A4",
        margin={"top": "12mm", "bottom": "12mm", "left": "11mm", "right": "11mm"},
        print_background=True,
    )
    browser.close()
print("wrote", OUT_PDF, OUT_PDF.stat().st_size, "bytes")
