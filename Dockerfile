FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of your application code
COPY ./pyjamaz ./pyjamaz

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

EXPOSE 8000
EXPOSE 9000

ENTRYPOINT ["python", "pyjamaz/cli.py"]
