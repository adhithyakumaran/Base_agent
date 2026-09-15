# P10.1 — Canonical ScoutAI warm orchestrator (single-client production image)
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LLM_ENABLED=false \
    PIP_NO_CACHE_DIR=1 \
    SCOUT_ENV=production \
    SCOUT_AGENT_BIND_HOST=127.0.0.1 \
    QA_RUNNER=playwright \
    QA_AUTOMATION_DIR=/app/apps/automation \
    QA_DISCOVERY_ROOT=/app/data/discovery-kb

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY services ./services
COPY apps/automation ./apps/automation
COPY data ./data
COPY scripts ./scripts
COPY plugins ./plugins

RUN pip install --upgrade pip \
 && pip install -e '.[browser,llm]' \
 && python -m playwright install --with-deps chromium

# Legacy base_agent.api is NOT the production ScoutAI entrypoint (patrol/tests only).
RUN useradd -m -u 10001 agent && chown -R agent:agent /app
USER agent

EXPOSE 43124
ENTRYPOINT ["python", "scripts/local_agent_server.py"]
CMD ["--host", "127.0.0.1", "--port", "43124"]
