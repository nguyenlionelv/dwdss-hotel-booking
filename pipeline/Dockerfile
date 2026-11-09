FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

COPY pipeline/requirements.txt ./pipeline/requirements.txt
RUN pip install --no-cache-dir -r pipeline/requirements.txt

COPY pipeline/ ./pipeline/
COPY scripts/ ./scripts/
COPY database/ ./database/
COPY docs/data_dictionary/operations_source_set.json ./docs/data_dictionary/operations_source_set.json

CMD ["python", "scripts/run_etl.py"]
