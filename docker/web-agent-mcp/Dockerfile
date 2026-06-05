FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    NO_PROXY=$NO_PROXY \
    http_proxy=$HTTP_PROXY \
    https_proxy=$HTTPS_PROXY \
    no_proxy=$NO_PROXY

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# uvのインストール
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
# Install only third-party dependencies, skip the project package itself
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src

# PYTHONPATH ensures src/web_agent_mcp is found directly (no editable install needed)
ENV PYTHONPATH=/app/src

CMD ["uv", "run", "--no-project", "python", "-m", "web_agent_mcp.server"]
