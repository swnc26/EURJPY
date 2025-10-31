# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# install dependensi sistem minimum (kadang pandas butuh lib tambahan)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# copy dan install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy seluruh project
COPY . .

# expose port (Back4App pakai env PORT, bukan fixed)
EXPOSE 8080

# jalankan aplikasi Flask
CMD ["python", "eurjpy_flask_app.py"]
