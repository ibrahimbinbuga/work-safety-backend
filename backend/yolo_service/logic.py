import time
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple

class WorkerState:
    """Tek bir işçinin durumunu takip eder"""
    def __init__(self, worker_id: int, position: list = None):
        self.worker_id = worker_id
        self.helmet_on = False
        self.vest_on = False
        self.head_visible = False
        self.last_update = datetime.now()
        self.last_position = position
        
    def update(self, helmet_detected: bool, vest_detected: bool, position: list = None):
        self.helmet_on = helmet_detected
        self.vest_on = vest_detected
        self.last_update = datetime.now()
        if position:
            self.last_position = position

class StateController:
    """İşçilerin durumunu yönetir ve ihlalleri tespit eder"""
    
    def __init__(self, min_log_interval: float = 1.0):
        self.workers: Dict[int, WorkerState] = {}
        self.min_log_interval = min_log_interval
        self.last_log_time = defaultdict(lambda: 0)
        self.next_worker_id = 1
        
        # Önceki ihlal durumlarını tutar
        self.previous_violation_states = {} 

    def _calculate_iou(self, box1: list, box2: list) -> float:
        """İki kutu arasındaki çakışma oranını (IoU) hesaplar"""
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        if inter_x_max <= inter_x_min or inter_y_max <= inter_y_min:
            return 0.0
        
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0

    def _check_overlap(self, person_box: list, detection_list: list, iou_threshold: float = 0.3) -> bool:
        for det in detection_list:
            if self._calculate_iou(person_box, det['box']) > iou_threshold:
                return True
        return False

    def _assign_worker_id(self, person_box: list) -> int:
        """Kişi kutusuna en yakın işçi ID'sini bulur veya yeni atar"""
        x_c, y_c = (person_box[0] + person_box[2]) / 2, (person_box[1] + person_box[3]) / 2
        
        best_id, min_dist = None, float('inf')

        for w_id, worker in self.workers.items():
            if not worker.last_position: continue
            # Son 2 saniyede görülmüş olmalı
            if (datetime.now() - worker.last_update).total_seconds() > 2.0: continue

            dist = ((x_c - worker.last_position[0])**2 + (y_c - worker.last_position[1])**2)**0.5
            if dist < 200 and dist < min_dist: # 200 piksel eşiği
                min_dist = dist
                best_id = w_id
        
        if best_id is not None: return best_id
        
        new_id = self.next_worker_id
        self.next_worker_id += 1
        return new_id

    def process_detections(self, detections: list) -> List[dict]:
        """
        Gelen kutuları işler ve YENİ başlayan ihlalleri liste olarak döner.
        Dönen her eleman veritabanına kaydedilecek bir olaydır.
        """
        violations_to_save = []
        
        # Gruplama
        person_dets = [d for d in detections if d['class_id'] == 3] # person
        helmet_dets = [d for d in detections if d['class_id'] == 0] # helmet
        vest_dets =   [d for d in detections if d['class_id'] == 1] # vest
        
        for p_det in person_dets:
            box = p_det['box']
            # Takip ID'si varsa kullan, yoksa konuma göre ata
            w_id = p_det.get('track_id') or self._assign_worker_id(box)
            
            # Nesneler kişiyle çakışıyor mu?
            has_helmet = self._check_overlap(box, helmet_dets)
            has_vest = self._check_overlap(box, vest_dets)
            
            # İşçiyi güncelle veya oluştur
            if w_id not in self.workers:
                self.workers[w_id] = WorkerState(w_id, [(box[0]+box[2])/2, (box[1]+box[3])/2])
            
            worker = self.workers[w_id]
            worker.update(has_helmet, has_vest, [(box[0]+box[2])/2, (box[1]+box[3])/2])
            
            # İhlal Durum Kontrolü
            prev_state = self.previous_violation_states.get(w_id, {'no_helmet': False, 'no_vest': False})
            
            # 1. KASK İHLALİ BAŞLADI MI? (Kask yok ve daha önce ihlal olarak işaretlenmemişse)
            if not has_helmet and not prev_state['no_helmet']:
                violations_to_save.append({
                    "worker_id": w_id,
                    "type": "no_helmet",
                    "confidence": p_det['confidence']
                })
            
            # 2. YELEK İHLALİ BAŞLADI MI?
            if not has_vest and not prev_state['no_vest']:
                violations_to_save.append({
                    "worker_id": w_id,
                    "type": "no_vest",
                    "confidence": p_det['confidence']
                })

            # Durumu güncelle
            self.previous_violation_states[w_id] = {
                'no_helmet': not has_helmet,
                'no_vest': not has_vest
            }
            
        return violations_to_save