# ---------- builder ----------
FROM python:3.13-slim-bookworm AS builder
WORKDIR /app

# OS deps for building Rust/Python extensions (and RocksDB features if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config curl ca-certificates \
    libffi-dev libssl-dev \
    clang cmake \
    zlib1g-dev libbz2-dev liblz4-dev libsnappy-dev libzstd-dev \
    && rm -rf /var/lib/apt/lists/*

# Speed up pip, prefer wheels where possible
ENV PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install --upgrade pip wheel setuptools && \
    # Try wheels first; fall back to source when necessary (Rust present)
    pip wheel -r requirements.txt -w /wheels --prefer-binary

# ---------- runtime ----------
FROM python:3.13-slim-bookworm
WORKDIR /app

# Runtime libs only (openssl for some deps; compression libs if rocksdict links dynamically)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 zlib1g libbz2-1.0 liblz4-1 libsnappy1v5 libzstd1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install /wheels/*

# Your app
COPY ./pyjamaz ./pyjamaz
RUN python -m compileall -b ./pyjamaz && find ./pyjamaz -name "*.py" -delete

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
ENTRYPOINT ["python","-m","pyjamaz.cli"]
