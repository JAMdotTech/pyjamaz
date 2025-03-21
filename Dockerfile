FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of your application code
COPY ./pyjamaz ./pyjamaz

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

ENTRYPOINT ["python", "pyjamaz/cli.py"]
