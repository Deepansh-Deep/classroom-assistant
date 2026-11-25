# 1) Build the Next.js frontend to static files
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend ./
RUN NEXT_TELEMETRY_DISABLED=1 npm run build

# 2) Python API that also serves the built frontend
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt "psycopg[binary]>=3.2"
COPY backend backend
COPY --from=web /web/out frontend/out
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn classroom.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
