FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app
COPY requirements.runtime.txt ./
# Docker build steps intentionally run as root inside the isolated image. The
# explicit flag acknowledges that boundary without emitting a misleading host
# environment warning; runtime still contains no package-manager operation.
RUN python -m pip install --root-user-action=ignore --no-cache-dir --require-hashes \
    -r requirements.runtime.txt
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]
CMD ["uvicorn", "job_search_core.app:app", "--host", "0.0.0.0", "--port", "8000"]
