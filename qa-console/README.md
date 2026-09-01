# Apex QA Console

Enterprise frontend for the Base Agent / QA Agent product.

## Features

- Prompt + prebuilt flow CTAs (sanity, ad-hoc, discover)
- Knowledge dump → data pills (text / md / json / csv / url)
- Live pipeline side panel with traces
- Daily morning sanity schedule (client-set time)
- Report channels: email, Teams, WhatsApp, Slack
- Export reports: JSON / Markdown / CSV / TXT
- Google-like history of client/agent actions
- Model picker (API gateway: Azure OpenAI, OpenAI, Anthropic, OCI, or LLM off)
- Token / usage tracking

## Run

```bash
cd qa-console
npm install
npm run dev -- --port 43123
```

Open [http://127.0.0.1:43123](http://127.0.0.1:43123).

Runs call the Python Base Agent in the parent repo (`python -m base_agent.api`) when available.
