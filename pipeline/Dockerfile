FROM python:3.12-slim

WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

COPY backend/requirements.txt ./backend/requirements.txt
COPY ml/requirements.txt ./ml/requirements.txt
COPY pipeline/requirements-dev.txt ./pipeline/requirements-dev.txt
COPY pipeline/ingestion/requirements.txt ./pipeline/ingestion/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    -r pipeline/requirements-dev.txt -r pipeline/ingestion/requirements.txt

# Source, pinned raw data and generated evidence are mounted by Compose.
CMD ["python", "scripts/prepare_app.py"]
