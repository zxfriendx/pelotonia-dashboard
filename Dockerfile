# Stage 1: Build React frontend
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir flask requests pillow psycopg[binary] psycopg_pool cachetools

COPY app/ app/
COPY --from=frontend-build /frontend/dist frontend/dist/

# AlloyDB: set ALLOYDB_DSN env var at deploy time
# No SQLite DB baked in — connects to AlloyDB at runtime
EXPOSE 8080

CMD ["python", "app/dashboard.py", "--port", "8080", "--host", "0.0.0.0"]
