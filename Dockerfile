FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Prepare data directory for SQLite
RUN mkdir -p /app/data

COPY src/ ./src/

ENV DB_PATH=/app/data/alerts.db
ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
