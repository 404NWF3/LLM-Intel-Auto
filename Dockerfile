# Unified runtime: intel_agent + Gradio console.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=8000 \
    IS_SANDBOX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=20

# Optional mirror, e.g. https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=
ARG PIP_TRUSTED_HOST=

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps BEFORE copying backend so code edits do not bust the pip layer.
# Keep the wheel cache across failed BuildKit attempts and retry the complete
# transaction when PyPI closes a large download early (IncompleteRead).
RUN --mount=type=cache,target=/root/.cache/pip \
    EXTRA_ARGS="" \
    && if [ -n "$PIP_INDEX_URL" ]; then EXTRA_ARGS="$EXTRA_ARGS -i $PIP_INDEX_URL"; fi \
    && if [ -n "$PIP_TRUSTED_HOST" ]; then EXTRA_ARGS="$EXTRA_ARGS --trusted-host $PIP_TRUSTED_HOST"; fi \
    && for ATTEMPT in 1 2 3; do \
        if python -m pip install --prefer-binary $EXTRA_ARGS \
            "claude-agent-sdk>=0.2.115,<0.3" \
            "pydantic>=2.7" \
            "pymongo>=4.6" \
            "gradio>=5.0.0,<6.0.0" \
            "matplotlib>=3.10.9"; then \
            break; \
        fi; \
        if [ "$ATTEMPT" -eq 3 ]; then exit 1; fi; \
        echo "pip install failed (attempt $ATTEMPT/3); retrying with cached wheels..."; \
        sleep 5; \
    done

COPY pyproject.toml README.md ./
COPY backend ./backend

EXPOSE 8000

CMD ["python", "-m", "console.app"]
