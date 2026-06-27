# syntax=docker/dockerfile:1

# --- Stage 1: build Tailwind CSS ---
FROM node:22-slim AS css
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY app/static/css/input.css app/static/css/input.css
COPY app/templates app/templates
COPY app/blueprints app/blueprints
RUN npm run build:css

# --- Stage 2: runtime ---
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TALLYWORTH_DATA_DIR=/data \
    FLASK_APP=wsgi.py

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY wsgi.py ./
COPY VERSION ./
COPY docker-entrypoint.sh ./
COPY --from=css /build/app/static/css/output.css ./app/static/css/output.css

RUN chmod +x docker-entrypoint.sh && \
    mkdir -p /data && \
    addgroup --system app && adduser --system --ingroup app app && \
    chown -R app:app /app /data
USER app

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "wsgi:app"]
