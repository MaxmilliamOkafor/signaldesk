# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY dashboard ./dashboard
COPY data ./data

EXPOSE 8000 8501

# Default: serve the API. docker-compose overrides for the dashboard service.
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
