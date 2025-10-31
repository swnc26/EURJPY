# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install dependensi sistem minimum
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Install dependensi Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh project
COPY . .

# Port 8080 sesuai Back4App health check
EXPOSE 8080

CMD ["python", "eurjpy_flask_app.py"]
