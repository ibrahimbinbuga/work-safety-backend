# Model Yönetim Sistemi - Teknik Özetç

## İşleyiş

### 1. **Admin (Developer) Modeli Yükler**
- Admin, `/api/model/upload` endpoint'ine model dosyası yükler
- Model her şirkete ayrı seçilmek üzere global olarak sisteme eklenir
- Modeller `model/weights/` klasörüne kaydedilir

### 2. **Admin Modeli Şirkete Atar**
- Model Management sayfasında admin:
  - En üstte şirket seçer
  - "Available Models" kısmında yüklenen modelleri görür
  - "Assign" butonuyla modeli seçilen şirkete atar
  - `/api/company/{company_code}/models/{model_id}/assign` endpoint'ine POST gönderilir
  - `CompanyModel` ilişki tablosuna yeni kayıt eklenir

### 3. **Admin Modeli Şirket için Aktifleştir**
- Admin, seçili şirkete atanmış modelleri "Assigned Models" kısmında görür
- "Activate" butonuyla modeli aktifleştir
- `/api/company/{company_code}/models/{company_model_id}/activate` endpoint'ine POST gönderilir
- Aynı şirketteki diğer aktif modeller otomatik olarak deaktif edilir
- Global `ACTIVE_MODEL_PATH` güncellenir
- Tüm kamera thread'leri yeni model ile yeniden başlatılır

### 4. **Kameralar Dinamik Olarak Yeni Model Kullanır**
- Model aktifleştirildiğinde `set_active_model_path()` çağrılır
- Çalışan tüm kamera thread'leri durdurulup yeni model ile yeniden başlatılır
- İlgili şirket için tespitler yeni model kullanılarak yapılır

## Database Şeması

### ModelMeta (Models Tablosu)
```
- id (PK)
- path (unique)
- version
- description
- uploaded_at
- is_active
- company_assignments (relationship to CompanyModel)
```

### Company
```
- id (PK)
- code (unique)
- name
- models (relationship to CompanyModel)
```

### CompanyModel (Many-to-Many İlişki)
```
- id (PK)
- company_id (FK)
- model_id (FK)
- is_active (bu şirket için aktif mi?)
- enabled_at
- company (relationship)
- model (relationship)
```

## API Endpoints

### Model Yönetimi
- `POST /api/model/upload` - Admin modeli yükler (auth required)
- `GET /api/models` - Tüm modelleri listeler (auth required)

### Company-Model Yönetimi  
- `GET /api/company/{company_code}/models` - Şirkete atanan modelleri listeler
- `POST /api/company/{company_code}/models/{model_id}/assign` - Model şirkete atar (admin)
- `POST /api/company/{company_code}/models/{company_model_id}/activate` - Modeli aktifleştir
- `POST /api/company/{company_code}/models/{company_model_id}/deactivate` - Modeli deaktif et

## Frontend Flow

### Model Management Sayfası
1. **Company Seçimi (Admin)**
   - Dropdown'dan şirket seçer
   - Sayfa seçili şirkete ait modelleri yükler

2. **Model Yükleme (Admin)**
   - Dosya seç > Versiyon gir > Açıklama gir > Yükle
   - `/api/model/upload` çağrılır

3. **Modelleri Yönet**
   - Sol: "Assigned Models" - Seçili şirkete atanan modeller
   - Sağ: "Available Models" - Yüklenen fakat atanmamış modeller
   - Assign butonuyla atama yap
   - Activate/Deactivate butonuyla kontrol et

4. **Test Detection**
   - Resim yükle
   - Aktif modelle test et
   - Sonuçları görüntüle

## Güvenlik

- `verify_company_access()` ile şirket erişimi kontrol edilir
- Admin'ler tüm şirketlere erişebilir
- Regular users sadece kendi şirketlerine atanan modelleri görebilir
- Model yükleme sadece admin'lere açık
