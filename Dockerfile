FROM python:3.11-slim

# OpenCV ve Ultralytics için sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Önce sadece requirements — Docker layer cache için
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Uygulama kodu
COPY backend/ ./backend/

# Model dosyaları (kamera inference için gerekli)
COPY model/ ./model/
COPY fall_model/ ./fall_model/

WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
