# Base Agent — Week 1 Technical Proposal

This repository contains the **Week 1 technical proposal** for a reusable **Base Agent runtime**.

It is **not** a design for the complete QA Agent.

Client documents describe an AI QA product that discovers an application from URL + credentials, learns business behaviour, executes natural-language tests, generates automation, and reports results. Those capabilities belong to **Week 2 plugins/skills**. Week 1 builds only the **deterministic-first agent core** that those plugins will attach to.

## What is in scope

- Reusable agent runtime (goal → state → route → execute → observe → decide → result)
- Plugin / skill / capability / tool contracts
- Tool registry and executor
- Hybrid routing (deterministic first, LLM only when required)
- Knowledge Base and Ground Truth **provider interfaces**
- Context management, decision engine, retries, loop prevention
- LangGraph/LangChain usage boundaries
- Observability and security foundations
- Test and evaluation strategy for the runtime, using **mock** plugins

## What is out of scope

- QA skills, security testing skills
- Browser / Playwright, API testing, database testing
- Oracle APEX-specific logic
- Full product features from the attached client requirement PDFs

## Document

Read the full proposal:

**[docs/BASE_AGENT_TECHNICAL_PROPOSAL.md](docs/BASE_AGENT_TECHNICAL_PROPOSAL.md)**

Source context (client requirements, used only to bound Week 2 vs Week 1):

- `uploads/QA_Agent_High_Level_Client_Requirements_4f8c.pdf`
- `uploads/Requirement_Overview_0c0a.pdf`

## Status

This repository currently delivers the **proposal**. Implementation of the Python runtime is the next step after proposal acceptance, following the staged roadmap in the document.
