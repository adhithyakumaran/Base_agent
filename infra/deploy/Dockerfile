# Enterprise runtime image for OCI Container Instances / OKE
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LLM_ENABLED=false \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY plugins ./plugins
COPY discovery/uat_ea/kb ./discovery/uat_ea/kb
COPY discovery/uat_ea/APPROVAL_CHECKLIST.md ./discovery/uat_ea/APPROVAL_CHECKLIST.md

RUN pip install --upgrade pip \
 && pip install -e '.[browser]' \
 && python -m playwright install --with-deps chromium

# Non-root
RUN useradd -m -u 10001 agent && chown -R agent:agent /app
USER agent

ENTRYPOINT ["python", "-m", "base_agent.api"]
CMD ["echo ready", "--kb-dir", "discovery/uat_ea/kb"]
