# Backend Test Rehberi

## 1. Backend'i Başlatma

```bash
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## 2. Backend Çalışıyor mu Kontrol Et

Tarayıcıda aç:
- http://127.0.0.1:8000 → `{"message": "SafetyWatch API running"}` görmeli
- http://127.0.0.1:8000/docs → FastAPI Swagger UI açılmalı

## 3. Kamera Durumunu Kontrol Et

Tarayıcıda aç:
- http://127.0.0.1:8000/api/cameras → Kamera listesi görmeli
- http://127.0.0.1:8000/api/camera/1/frame-status → Frame durumunu gösterir

## 4. Stream Test Et

Tarayıcıda aç:
- http://127.0.0.1:8000/api/camera/1/stream → Canlı görüntü stream'i görmeli

## 5. Console Log'larını Kontrol Et

Backend başlatıldığında şunları görmeli:
- `[startup] Creating DB tables...`
- `[consumer] Violation consumer started.`
- `[CameraRunner] Starting camera 1 -> 0`
- `[start_camera_thread] Started camera thread for 1`

Eğer hata varsa:
- `[CameraRunner][Camera 1] Error encoding frame: ...` şeklinde görünecek

## 6. Sorun Giderme

### Frame görünmüyorsa:
1. Backend console'da hata var mı kontrol et
2. http://127.0.0.1:8000/api/camera/1/frame-status endpoint'ini kontrol et
3. Kamera thread'i çalışıyor mu kontrol et (console log'larına bak)
4. Model dosyası doğru yolda mı kontrol et (`../model/weights/best.pt`)

### Stream yüklenmiyorsa:
1. Browser console'u aç (F12) ve hataları kontrol et
2. Network tab'ında stream request'ini kontrol et
3. CORS hatası varsa backend CORS ayarlarını kontrol et

