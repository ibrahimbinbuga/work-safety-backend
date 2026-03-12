# Work Safety System - Setup & Installation Guide

Bu dokümanda, Work Safety System uygulamasını sıfırdan kurmak ve çalıştırmak için gereken tüm adımlar detaylı olarak anlatılmıştır.

## Table of Contents
1. [Sistem Gereksinimleri](#sistem-gereksinimleri)
2. [Seçenek A: Sıfırdan Kurulum](#seçenek-a-sıfırdan-kurulum)
3. [Seçenek B: Mevcut Veritabanı ile Başlama](#seçenek-b-mevcut-veritabanı-ile-başlama)
4. [Uygulamayı Çalıştırma](#uygulamayı-çalıştırma)
5. [Test Verileri](#test-verileri)
6. [Troubleshooting](#troubleshooting)

---

## Sistem Gereksinimleri

Başlamadan önce aşağıdakilerin kurulu olduğundan emin olun:

- **Python 3.9+** - [Download](https://www.python.org/downloads/)
- **Node.js 18+** - [Download](https://nodejs.org/)
- **Docker & Docker Compose** (Veritabanı için önerilir) - [Download](https://www.docker.com/)
- **PostgreSQL 15** (Docker kullanmıyorsanız lokal kurulum gerekli)
- **Git** - Version control için

Versiyonları kontrol edin:
```bash
python --version
node --version
docker --version
```

---

## Seçenek A: Sıfırdan Kurulum

Bu seçeneği kullanın eğer:
- ✅ Tamamen yeni bir ortam kuruyor musunuz
- ✅ Veritabanı henüz oluşturulmamıştır
- ✅ Baştan başlamak istiyorsunuz

### Adım 1: Projeyi Klonlayın

```bash
# Çalışmak istediğiniz herhangi bir klasöre gidin
cd <your-workspace-folder>

# Projeyi klonlayın
git clone <repo-url>
cd work-safety-backend
```

Not: Bu dokümanda URL standardı olarak `localhost` kullanılmıştır.
`127.0.0.1` ve `localhost` aynı makineyi işaret eder; ekip içinde karışıklığı önlemek için tek formatta kalın.

### Adım 2: Docker ile Veritabanını Başlatın

Docker container'da PostgreSQL veritabanını çalıştırın:

```bash
# Docker container'ı başlat
docker-compose up -d

# Veritabanının başladığını kontrol et (15-30 saniye beklemelidir)
docker-compose logs db
```

Çıktıda şuna benzer bir mesaj görmelisiniz:
```
database system is ready to accept connections
```

#### Veritabanına Bağlantı Bilgileri:
- **Host:** localhost
- **Port:** 5432
- **Username:** admin
- **Password:** password123
- **Database:** safety_analysis_db

#### PgAdmin (Opsiyonel - Veritabanını Web Üzerinden Yönetmek İçin):
- **URL:** http://localhost:5050
- **Email:** admin@admin.com
- **Password:** root

### Adım 3: Backend Environment Kurulumu

Python virtual environment oluşturun ve paketleri yükleyin:

```bash
# Backend klasörüne gir
cd backend

# Virtual environment oluştur
python -m venv venv

# Virtual environment'ı aktifleştir
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Gerekli paketleri yükle
pip install -r requirements.txt
```

### Adım 4: .env Dosyasını Oluşturun

Backend klasöründe `.env` dosyası oluşturun:

```bash
cd ..
```

Proje kökünde `.env` dosyası oluşturun (veya güncelleyin):

```env
# Database Configuration
DB_USER=admin
DB_PASSWORD=password123
DB_HOST=localhost
DB_PORT=5432
DB_NAME=safety_analysis_db

# JWT Configuration
SECRET_KEY=your-secret-key-change-this-in-production-make-it-long-and-random-string
ALGORITHM=HS256

# CORS Configuration
FRONTEND_URL=http://localhost:5173
```

**Not:** Production için `SECRET_KEY`'i güçlü bir rastgele string ile değiştirin.

### Adım 5: Veritabanını Başlatın

Veritabanını oluşturun ve test verilerini ekleyin:

```bash
# Backend klasöründe olduğundan emin ol
cd backend

# Virtual environment aktif olduğundan emin ol (Windows)
venv\Scripts\activate

# Veritabanını başlat
python init_db.py
```

**Başarılı sonuç örneği:**
```
============================================================
🔄 DATABASE INITIALIZATION STARTING...
============================================================

🔄 Creating all tables...
✅ Tables created successfully

📝 Creating companies...
  ✅ ADMIN - System Admin
  ✅ COMPANY001 - ABC İnşaat
  ✅ COMPANY002 - XYZ Fabrika
  ✅ COMPANY003 - DEF Lojistik
  ✅ COMPANY004 - GHI Mayın

👤 Creating users...
  ✅ admin@system.com (admin) -> ADMIN
  ✅ user1@abc.com (user) -> COMPANY001
  ✅ manager1@abc.com (manager) -> COMPANY001
  ... ve daha fazlası

✨ DATABASE INITIALIZATION COMPLETE!
```

### Adım 6: Backend'i Çalıştırın

```bash
# Backend klasöründe olduğundan emin ol
# Virtual environment aktif olduğundan emin ol

uvicorn main:app --reload
```

Başarılı çıktı:
```
INFO:     Uvicorn running on http://localhost:8000
INFO:     Application startup complete
```

### Adım 7: Frontend Environment Kurulumu

Yeni bir terminal penceresi açın (backend çalışır durumda kalmalı):

```bash
# Frontend klasörüne gir
cd frontend

# Node paketlerini yükle
npm install

# Frontend URL konfigürasyonu (frontend/.env)
# Backend farklı host/port'ta çalışıyorsa bu değeri güncelleyin.
echo VITE_API_URL=http://localhost:8000 > .env

# Frontend'i geliştirme modunda başlat
npm run dev
```

Başarılı çıktı:
```
VITE v... ready in ... ms

➜  Local:   http://localhost:5173/
```

### Adım 8: Uygulamaya Erişin

Tarayıcınızda açın:
```
http://localhost:5173
```

---

## Seçenek B: Mevcut Veritabanı ile Başlama

Bu seçeneği kullanın eğer:
- ✅ Veritabanı zaten kurulu ve dolu
- ✅ Sadece uygulamayı çalıştırmak istiyorsunuz
- ✅ Verileri yeniden başlatmak istemiyorsunuz

### Adım 1: Veritabanının Çalışıp Çalışmadığını Kontrol Edin

```bash
# Eğer Docker kullanıyorsanız
docker-compose ps

# Çıktı şuna benzer olmalı:
# NAME          STATUS
# safety_db     Up (healthy)
# safety_pgadmin Up
```

Eğer container'lar durmuşsa, başlatın:
```bash
docker-compose up -d
```

### Adım 2: Backend Setup

```bash
# Backend klasöründe olduğundan emin ol
cd backend

# Virtual environment oluştur (varsa atla)
python -m venv venv

# Virtual environment'ı aktifleştir (Windows)
venv\Scripts\activate

# Paketleri yükle (varsa atla)
pip install -r requirements.txt
```

### Adım 3: Backend'i Çalıştırın

```bash
# Backend klasöründe, virtual environment aktif
uvicorn main:app --reload
```

### Adım 4: Frontend Setup

Yeni terminal:

```bash
# Frontend klasöründe
cd frontend

# Paketleri yükle (varsa atla)
npm install

# Geliştirme sunucusunu başlat
npm run dev
```

### Adım 5: Uygulamaya Erişin

```
http://localhost:5173
```

---

## Uygulamayı Çalıştırma

### Terminal Setup (3 pencere gerekli)

#### Terminal 1: PostgreSQL Veritabanı
```bash
# Proje kökünde
docker-compose up

# Detach modunda çalıştırmak için:
docker-compose up -d
```

#### Terminal 2: Backend (FastAPI)
```bash
cd backend

# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate

uvicorn main:app --reload
```

**Successful startup message:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete
INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
```

#### Terminal 3: Frontend (Vite)
```bash
cd frontend
npm run dev
```

**Successful startup message:**
```
➜  Local:   http://localhost:5173/
➜  press h to show help
```

### Erişim Adresleri

| Hizmet | URL | Açıklama |
|--------|-----|----------|
| **Frontend** | http://localhost:5173 | React uygulaması |
| **Backend API** | http://localhost:8000 | FastAPI sunucusu |
| **API Docs** | http://localhost:8000/docs | Swagger UI (API test için) |
| **PgAdmin** | http://localhost:5050 | Veritabanı yönetimi (opsiyonel) |

---

## Test Verileri

### Otomatik Olarak Oluşturulan Test Kullanıcıları

`init_db.py` çalıştırıldıktan sonra aşağıdaki kullanıcılar otomatik olarak oluşturulur:

#### 🔓 Super Admin (Tüm Şirketleri Yönetebilir)
```
Company Code: ADMIN
Email: admin@system.com
Password: admin123
Rol: Admin
```

#### 🏢 COMPANY001 (ABC İnşaat)
```
User: user1@abc.com / password123
Manager: manager1@abc.com / password123
```

#### 🏢 COMPANY002 (XYZ Fabrika)
```
User: user2@xyz.com / password123
Manager: manager2@xyz.com / password123
```

#### 🏢 COMPANY003 (DEF Lojistik)
```
User: user3@def.com / password123
Manager: manager3@def.com / password123
```

#### 🏢 COMPANY004 (GHI Mayın)
```
User: user4@ghi.com / password123
Manager: manager4@ghi.com / password123
```

### Admin Özellikleri

Admin giriş yapınca:
1. Sidebar'da "Select Company" dropdown göreceğiniz
2. Bir şirket seçmek zorunlu (önce warning gösterecek)
3. Şirket seçince otomatik Dashboard'a yönlendirileceksiniz
4. Farklı şirket seçmek için dropdown'dan seçip "Select" butonuna basabilirsiniz

---

## Troubleshooting

### Sorun 1: Veritabanı Bağlantı Hatası

**Hata:** `postgresql.asyncpg.exceptions.CannotConnectNowError`

**Çözüm:**
```bash
# Docker container'ın çalışıp çalışmadığını kontrol et
docker ps

# Container'ı yeniden başlat
docker-compose restart db

# 30 saniye bekle ve tekrar dene
```

### Sorun 2: Port Zaten Kullanımda

**Hata:** `Address already in use (Errno 48)`

**Çözüm:**
```bash
# Kullanımda olan port'u bul (örneğin 5432 - PostgreSQL)
netstat -ano | findstr :5432

# Process'i öldür (PID'yi kullan)
taskkill /PID <PID> /F

# veya Docker container'ı durdur
docker-compose down
```

### Sorun 3: Virtual Environment Hataları

**Hata:** `No module named 'venv'`

**Çözüm:**
```bash
# Python'u yeniden kur veya pip ile venv yükle
python -m pip install --upgrade pip
python -m venv venv
```

### Sorun 4: Node_modules Hataları

**Hata:** `npm ERR! code ERESOLVE`

**Çözüm:**
```bash
cd frontend

# Cache'i temizle
npm cache clean --force

# node_modules'ı sil
# Windows (PowerShell):
Remove-Item -Recurse -Force node_modules
# macOS/Linux:
rm -rf node_modules

# Yeniden yükle
npm install

# veya force bayrağı ile
npm install --legacy-peer-deps
```

### Sorun 5: CORS Hataları

**Hata:** `Access to XMLHttpRequest blocked by CORS`

**Kontrol Edin:**
```bash
# Backend .env dosyasında bu satırın olduğundan emin ol:
# FRONTEND_URL=http://localhost:5173

# Frontend .env dosyasında bu satırın olduğundan emin ol:
# VITE_API_URL=http://localhost:8000

# Backend main.py'de CORSMiddleware kurulumu kontrol et
```

### Sorun 6: React Hooks Hatası

**Hata:** `React has detected a change in the order of Hooks`

**Çözüm:**
- Frontend'i yeniden başlat: `npm run dev`
- Browser cache'ini temizle (F12 → Application → Clear Storage)
- Sayfayı hard refresh yap: `Ctrl + Shift + R`

### Sorun 7: "Please select a company" Uyarısı

**Durum:** Admin giriş yaptı ama şirket seçmiyor

**Beklenen Davranış:**
- ✅ Sidebar'da "Select Company" dropdown görülmelidir
- ✅ Şirketi seçiniz
- ✅ "Select" butonuna basın
- ✅ Loading spinner görünmelidir
- ✅ Dashboard'a yönlendirileceksiniz

---

## Geliştirme İpuçları

### API Test Etme

Swagger UI kullanarak API'ı test edin:
```
http://localhost:8000/docs
```

### Database İçeriğini Kontrol Etme

PgAdmin kullanarak:
```
http://localhost:5050
```

Login:
- Email: admin@admin.com
- Password: root

### Logs İzleme

**Backend Logs:**
Terminal 2'de `uvicorn` çıktısını izleyin

**Database Logs:**
```bash
docker-compose logs db
```

**Frontend Logs:**
Browser console'unu açın (F12)

### Veritabanını Sıfırla

Tüm verileri silip yeniden başlamak istiyorsanız:

**Hızlı Yol (Önerilir):**
```bash
# Backend klasöründe, virtual environment aktif
python init_db.py
```
Bu komut otomatik olarak tüm verileri temizler ve yeniden oluşturur.

**Tam Sıfırlama (Tüm Container'lar):**
```bash
# Container'ları ve volume'ları kaldır
docker-compose down -v

# Yeniden başlat
docker-compose up -d

# Backend'de init_db.py'ı çalıştır
cd backend
python init_db.py
```

---

## İlave Komutlar

### Backend Komutları

```bash
# Backend klasöründe virtual environment aktif

# Veritabanını başlat (ilk kez veya sıfırlamak için)
python init_db.py

# Sunucuyu başlat (otomatik reload)
uvicorn main:app --reload

# Sunucuyu belirli port'ta başlat
uvicorn main:app --reload --port 8001

# Production build
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend Komutları

```bash
# Frontend klasöründe

# Geliştirme sunucusu
npm run dev

# Build
npm run build

# Preview (build'i test etmek için)
npm run preview

# Lint
npm lint
```

### Docker Komutları

```bash
# Başlat
docker-compose up -d

# Durdur
docker-compose down

# Logs izle
docker-compose logs -f

# Container'ı yeniden başlat
docker-compose restart db

# Tüm veriyi sil (volume dahil)
docker-compose down -v
```

---

## Kontrol Listesi

Başarılı kurulum için:

- [ ] Docker/PostgreSQL çalışıyor (port 5432)
- [ ] PgAdmin erişilebiliyor (port 5050)
- [ ] Backend virtual environment aktif
- [ ] Backend paketleri yüklü (`pip list`)
- [ ] .env dosyası doğru konfigüre edilmiş
- [ ] init_db.py başarıyla çalıştı
- [ ] Backend sunucu çalışıyor (port 8000)
- [ ] Swagger UI erişilebiliyor (http://localhost:8000/docs)
- [ ] Frontend paketleri yüklü (`npm list`)
- [ ] Frontend sunucu çalışıyor (port 5173)
- [ ] Tarayıcıda http://localhost:5173 açılıyor
- [ ] Test kullanıcılarıyla giriş yapabiliyor
- [ ] Admin şirket seçebiliyor
- [ ] Regular user kendi şirketini görüyor

---

## İletişim & Destek

Sorun yaşadığınız takdirde:

1. Yukarıdaki Troubleshooting bölümünü kontrol edin
2. Docker logs'ları inceleyin: `docker-compose logs`
3. Browser console'unu açın (F12) ve hataları kontrol edin
4. Backend terminal çıktısını kontrol edin

---

**Son Güncelleme:** 2026-01-28

