# Stage 1: build the React frontend
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python backend serves the API and the built frontend
FROM python:3.10-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt 
RUN pip install --no-cache-dir --default-timeout=100 --retries 10 -r backend/requirements.txt
COPY backend/ backend/
COPY seed/ seed/
COPY --from=frontend /app/frontend/dist frontend/dist
WORKDIR /app/backend
ENV PORT=10000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]