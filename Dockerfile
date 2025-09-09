# ---------- Builder: heeft Rust toolchain + build deps ----------
FROM python:3.14-rc-slim-bookworm AS builder

WORKDIR /app

# Systeemdeps om wheels te bouwen (PyO3/openssl/ffi/etc.)
# - curl/ca-certificates: om rustup te installeren
# - build-essential/gcc/g++/pkg-config: algemene C/C++ build toolchain
# - libssl-dev/libffi-dev: headers voor veelgebruikte bindings
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl ca-certificates \
      build-essential gcc g++ pkg-config \
      libssl-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Rust toolchain (minimal profile, stable)
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --profile minimal --default-toolchain stable

# (Optioneel maar handig) Maturin beschikbaar maken als sommige deps dat gebruiken
# Je kunt deze regel weglaten als je het niet nodig hebt.
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir maturin

# Gebruik een venv zodat we de omgeving eenvoudig kunnen kopiëren naar de runtime image
ENV VENV=/venv
RUN python -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

# Installeer Python-deps (Rust-extensies worden hier gebouwd)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
     pip install --no-cache-dir -r requirements.txt

# Kopieer broncode en compileer .py -> .pyc (bytecode)
COPY ./pyjamaz ./pyjamaz
RUN python -m compileall -b ./pyjamaz && \
    find ./pyjamaz -name "*.py" -type f -delete

# ---------- Runtime: slank, zonder Rust toolchain ----------
FROM python:3.14-rc-slim-bookworm AS runtime

WORKDIR /app

# Alleen runtime libs (géén -dev headers)
# libssl3/libffi8 zijn runtime-varianten voor Bookworm.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libssl3 libffi8 && \
    rm -rf /var/lib/apt/lists/*

# Zet de gecompileerde venv en app over vanuit de builder
ENV VENV=/venv
COPY --from=builder $VENV $VENV
COPY --from=builder /app/pyjamaz /app/pyjamaz

# Standaard Python env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    PATH="$VENV/bin:$PATH"

ENTRYPOINT ["python", "pyjamaz/cli.pyc"]
