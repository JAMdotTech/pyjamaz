FROM python:3.12-slim

# Install system dependencies for building Rust projects
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Rust using rustup
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of your application code
COPY ./pyjamaz ./pyjamaz

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

ENTRYPOINT ["python", "pyjamaz/cli.py"]
