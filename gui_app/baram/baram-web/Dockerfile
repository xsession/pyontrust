# ── Baram-Web Docker Image ─────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="baram-web"
LABEL description="BaramFlow Web — Flask + Vanilla JS CFD frontend"

WORKDIR /app

# System deps for lxml & HDF5
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libxml2 libxslt1.1 libhdf5-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Default port
EXPOSE 5000

# Non-root user for security
RUN useradd -m baramweb
USER baramweb

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "5000"]
