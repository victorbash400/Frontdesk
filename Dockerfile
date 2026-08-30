FROM node:22-bookworm-slim AS browser-runtime

WORKDIR /build/infra/browser-runtime
RUN corepack enable
COPY infra/browser-runtime/package.json infra/browser-runtime/pnpm-lock.yaml infra/browser-runtime/pnpm-workspace.yaml ./
COPY patches /build/patches
RUN pnpm install --prod --frozen-lockfile --ignore-scripts

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update && apt-get install --no-install-recommends -y libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=browser-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=browser-runtime /build/infra/browser-runtime/node_modules ./node_modules
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./backend/app
COPY backend/agents ./backend/agents
COPY backend/tools ./backend/tools
COPY backend/meetings ./backend/meetings

RUN python -m compileall -q backend \
    && PYTHONPATH=/app/backend python -c "from app.main import app; assert app.title == 'Front Desk API'" \
    && node_modules/.bin/playwright-mcp --help > /dev/null

CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8080}"]
