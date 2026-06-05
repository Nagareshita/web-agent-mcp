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
    # Playwright/Chromium system dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libwayland-client0 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# uvのインストール
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
# Install only third-party dependencies, skip the project package itself
RUN uv sync --frozen --no-dev --no-install-project

# Install Playwright and Chromium browser
RUN uv run --no-project playwright install chromium

COPY src ./src

# PYTHONPATH ensures src/web_agent_mcp is found directly (no editable install needed)
ENV PYTHONPATH=/app/src

CMD ["uv", "run", "--no-project", "python", "-m", "web_agent_mcp.server"]
