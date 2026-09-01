#!/usr/bin/env python3
"""Morning patrol — Azure schedule entrypoint.

Writes a markdown/json report under artifacts/morning_report and prints
delivery targets (email/whatsapp). Live SMTP/Twilio/Teams send happens when
secrets are present in the Azure/OCI environment.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from base_agent.api import build_default_runtime


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "artifacts" / "morning_report"
    out.mkdir(parents=True, exist_ok=True)

    runtime = build_default_runtime(kb_dir=str(root / "discovery" / "uat_ea" / "kb"))
    goals = [
        "health check endless aisle technical readiness",
        "login probe",
        "assemble report bundle",
    ]
    results = []
    for goal in goals:
        r = runtime.run(goal)
        results.append(r.model_dump())

    email = os.environ.get("REPORT_EMAIL", "adhithyakumaran2005@gmail.com")
    whatsapp = os.environ.get("REPORT_WHATSAPP", "+919965985951")
    teams = os.environ.get("TEAMS_WEBHOOK_URL", "")

    md = [
        f"# Morning QA Patrol — {datetime.now(timezone.utc).isoformat()}",
        "",
        f"- Email target: `{email}`",
        f"- WhatsApp target: `{whatsapp}`",
        f"- Teams webhook configured: **{'yes' if teams else 'no'}**",
        "",
    ]
    for r in results:
        md.append(f"## {r.get('goal')}")
        md.append(f"- Conclusion: **{r.get('conclusion')}**")
        md.append(f"- Reason: `{r.get('reason_code')}`")
        md.append(f"- Tools: {r.get('tool_calls')} · LLM: {r.get('llm_calls')}")
        md.append("")

    (out / "report.md").write_text("\n".join(md), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (out / "delivery_targets.json").write_text(
        json.dumps({"email": email, "whatsapp": whatsapp, "teams_configured": bool(teams)}, indent=2),
        encoding="utf-8",
    )
    print("Morning patrol complete →", out)
    print("Deliver to:", email, whatsapp)


if __name__ == "__main__":
    main()
