FROM python:3.12-slim-bookworm

WORKDIR /app

# Install OS-level dependencies securely
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*


# Install project requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY ./pyjamaz ./pyjamaz

# Compile app and remove source code
RUN python -m compileall -b ./pyjamaz && \
    find ./pyjamaz -name "*.py" -type f -delete

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

ENTRYPOINT ["python", "pyjamaz/cli.pyc"]
