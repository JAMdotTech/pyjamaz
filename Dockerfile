FROM python:3.14-rc-slim-bookworm

WORKDIR /app

# Install OS-level dependencies securely
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*


# Install project requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY ./pyjamaz ./pyjamaz
COPY ./scripts ./scripts

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

RUN mkdir -p /app/numba-cache
ENV NUMBA_CACHE_DIR="/app/numba-cache/"

# https://numba.pydata.org/numba-doc/dev/reference/envvars.html
ENV NUMBA_CACHE=1
ENV NUMBA_DISABLE_PERFORMANCE_WARNINGS=1
ENV NUMBA_BOUNDSCHECK=0
ENV NUMBA_EAGERNESS=1
ENV NUMBA_LOOP_VECTORIZE=1
ENV NUMBA_ENABLE_AVX=1
ENV NUMBA_OPT=3
ENV NUMBA_DEBUG=0
ENV NUMBA_DEBUGINFO=0

ENV PVM_INTERPRETER=NUMBA_AOT

# Trigger compilation of the numba PVM interpreter
RUN ./scripts/build_numba_aot.sh

RUN python -m compileall -b -d /app ./pyjamaz && \
 find ./pyjamaz -name "*.py" -type f \
   ! -path "./pyjamaz/pvm/interpreters/numba/*" \
   -delete && \
 rm -rf ./pyjamaz/pvm/interpreters/numba/__pycache__ && \
 chmod -R 777 /app/numba-cache && \
 chmod -R 777 /app/pyjamaz/pvm/interpreters/numba

ENTRYPOINT ["python", "pyjamaz/cli.pyc"]
