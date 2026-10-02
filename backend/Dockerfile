FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY campaia_core ./campaia_core
COPY db ./db
COPY scripts ./scripts

RUN useradd --create-home --uid 10001 campaia \
    && chown -R campaia:campaia /app
USER campaia

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers"]
