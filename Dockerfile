# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy seluruh project
COPY . .

# gunakan port dinamis dari Back4App (tidak hardcoded)
EXPOSE 8080

# jalankan aplikasi sesuai procfile
CMD ["python", "eurjpy_flask_app.py"]
