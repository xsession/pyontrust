# ═══════════════════════════════════════════════════════════════
# pyontrust Lab Bench — container image
# Build:   docker build -t pyontrust/lab-bench .
# Run:     docker compose up --build        (see docker-compose.yml)
# ═══════════════════════════════════════════════════════════════
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYONTRUST_HOST=0.0.0.0 \
    PYONTRUST_PORT=5200 \
    PYONTRUST_ARTIFACTS=/app/artifacts

WORKDIR /app

# System deps: libusb (Seek Thermal & other USB instruments), V4L2 headers
RUN apt-get update && apt-get install -y --no-install-recommends \
        libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

# Core has zero mandatory deps; extras are opt-in. Override at build time:
#   docker build --build-arg PYONTRUST_EXTRAS=gui,analysis,thermal .
ARG PYONTRUST_EXTRAS=gui,analysis
RUN pip install --upgrade pip && \
    pip install ".[${PYONTRUST_EXTRAS}]"

RUN useradd -m -u 1000 bench || true
USER bench
VOLUME ["/app/artifacts"]
EXPOSE 5200

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5200', timeout=3).status==200 else 1)" || exit 1

CMD ["python", "-m", "pyontrust.gateway.app", "--host", "0.0.0.0", "--port", "5200"]
