FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/tasks.db \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY main.py ./

RUN mkdir -p /data /app/logs

CMD ["python", "-m", "bot"]
