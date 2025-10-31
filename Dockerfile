# syntax=docker/dockerfile:1

# Gunakan base image Python
FROM python:3.11-slim

# Set direktori kerja di dalam container
WORKDIR /app

# Salin file requirements.txt dan install dependensi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh isi project ke dalam container
COPY . .

# Tentukan port yang digunakan aplikasi (5000 default Flask)
EXPOSE 5000

# Jalankan aplikasi sesuai perintah di Procfile
CMD ["python", "eurjpy_flask_app.py"]
