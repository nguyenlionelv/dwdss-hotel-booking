FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
COPY ml/requirements.txt ./ml/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY ml ./ml
COPY pipeline ./pipeline
ARG MODEL_ARTIFACT_PATH=artifacts/ml_serving/models
ARG MODEL_SNAPSHOT_PATH=artifacts/ml_serving/snapshot
ARG DSS_POLICY_PATH=backend/app/services/decision_engine
COPY ${MODEL_ARTIFACT_PATH} ./artifacts/ml_serving/models
COPY ${MODEL_SNAPSHOT_PATH} ./artifacts/ml_serving/snapshot
COPY ${DSS_POLICY_PATH}/policy.json ./artifacts/dss_policies/policy.json
COPY ${DSS_POLICY_PATH}/allocation_policy.json ./artifacts/dss_policies/allocation_policy.json
ENV DWDSS_MODEL_DIR=/app/artifacts/ml_serving/models \
    DWDSS_SNAPSHOT_DIR=/app/artifacts/ml_serving/snapshot \
    DWDSS_DECISION_POLICY=/app/artifacts/dss_policies/policy.json \
    DWDSS_ALLOCATION_POLICY=/app/artifacts/dss_policies/allocation_policy.json

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import json, sys, urllib.request; health = json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)); sys.exit(0 if health.get('db_connected') is True else 1)"]

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
