FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt pyproject.toml /app/
COPY src /app/src
RUN pip install --no-cache-dir -r requirements.txt \
  && pip install --no-cache-dir /app \
  && python -c "import jellyplexsync; from jellyplexsync.web import start_web; print('ok', jellyplexsync.__version__)"

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    DATA_DIR=/data \
    SLEEP_DURATION=300 \
    WEB_ENABLED=true \
    WEB_PORT=8788

VOLUME ["/data"]
EXPOSE 8788
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8788/health', timeout=3)"

CMD ["python", "-m", "jellyplexsync"]
