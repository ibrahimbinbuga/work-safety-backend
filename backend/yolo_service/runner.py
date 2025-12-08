import sys
import os
import cv2
import asyncio
import datetime
from ultralytics import YOLO

# Üst dizindeki modülleri görebilmek için yol ayarı
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import AsyncSessionLocal
from models import Detection, Camera
from yolo_service.logic import StateController

# Fotoğrafların kaydedileceği yer (Frontend görsün diye public klasörüne atıyoruz)
SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "public", "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

async def save_violation_to_db(violation_data, image_filename):
    """Veritabanına kaydetme işlemi"""
    async with AsyncSessionLocal() as session:
        # Örnek olarak ilk kameraya bağlıyoruz (ID=1)
        # Gerçek senaryoda bu script hangi kameraya bağlıysa onun ID'si olur.
        new_violation = Detection(
            camera_id=1, 
            detection_type=violation_data['type'],
            confidence=violation_data['confidence'],
            is_violation=True,
            snapshot_path=f"/snapshots/{image_filename}", # React bu yoldan okuyacak
            timestamp=datetime.datetime.now()
        )
        session.add(new_violation)
        await session.commit()
        print(f"✅ [DB SAVED] Violation: {violation_data['type']} - Worker {violation_data['worker_id']}")

def run_camera_system():
    # YOLO Model Yolu (Kendi yolunu kontrol et)
    model_path = "yolo11n.pt" # veya "runs/helmet_detection7/weights/best.pt"
    try:
        model = YOLO(model_path)
    except:
        print(f"Model bulunamadı: {model_path}. Standart model indiriliyor...")
        model = YOLO("yolo11n.pt") 

    controller = StateController()
    
    # 0: Webcam, veya video dosyası yolu
    cap = cv2.VideoCapture(0)
    
    print("🎥 Kamera Sistemi Başlatıldı (Çıkış için 'q' bas)...")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # YOLO Tahmini
        results = model.track(frame, persist=True, verbose=False, classes=[0,1,3]) # 0:helmet, 1:vest, 3:person (sınıf ID'lerini kendi modeline göre ayarla)
        
        detections = []
        for result in results:
            # Kutuları çiz (Ekranda görmek için)
            frame_visual = result.plot()
            
            if result.boxes:
                for box in result.boxes:
                    detections.append({
                        'class_id': int(box.cls[0]),
                        'confidence': float(box.conf[0]),
                        'box': box.xyxy[0].tolist(),
                        'track_id': int(box.id[0]) if box.id is not None else None
                    })

        # Logic katmanına gönder
        violations = controller.process_detections(detections)

        # İhlal varsa kaydet
        if violations:
            for v in violations:
                # 1. Fotoğrafı Kaydet
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"violation_{v['worker_id']}_{v['type']}_{timestamp}.jpg"
                save_path = os.path.join(SNAPSHOT_DIR, filename)
                
                # O anki kareyi diske yaz
                cv2.imwrite(save_path, frame)
                
                # 2. Veritabanına Yaz (Asenkron fonksiyonu senkron döngüde çağırmak için)
                asyncio.run(save_violation_to_db(v, filename))

        # Ekranda Göster
        cv2.imshow("SafetyWatch AI Monitor", frame_visual)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_camera_system()