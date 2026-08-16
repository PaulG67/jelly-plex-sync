FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt pyproject.toml /app/
COPY src /app/src
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir /app

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    SLEEP_DURATION=300

VOLUME ["/data"]
EXPOSE 8788
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "from pathlib import Path; import sys; sys.exit(0 if Path('/data/healthy').exists() else 1)"

CMD ["python", "-m", "jellyplexsync"]
