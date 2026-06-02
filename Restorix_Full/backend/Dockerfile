FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

RUN adduser --disabled-password --gecos "" appuser
RUN mkdir -p /var/lib/dbshield/restore-tmp \
    && chown appuser:appuser /var/lib/dbshield/restore-tmp \
    && chmod 770 /var/lib/dbshield/restore-tmp
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
