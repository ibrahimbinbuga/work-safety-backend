from datetime import datetime
from collections import defaultdict
import time
from typing import Dict, List, Tuple


class WorkerState:
    def __init__(self, worker_id: int, position: list = None):
        self.worker_id = worker_id
        self.helmet_on = False
        self.vest_on = False
        self.head_visible = False
        self.last_update = datetime.now()
        self.last_position = position
        self.last_logged = None

    def update(self, helmet_detected: bool, vest_detected: bool, position: list = None) -> Tuple[bool, bool]:
        helmet_changed = self.helmet_on != helmet_detected
        vest_changed = self.vest_on != vest_detected
        self.helmet_on = helmet_detected
        self.vest_on = vest_detected
        self.last_update = datetime.now()
        if position:
            self.last_position = position
        return helmet_changed, vest_changed

    def get_status(self) -> Dict:
        return {
            "worker_id": self.worker_id,
            "helmet": "ON" if self.helmet_on else "OFF",
            "vest": "ON" if self.vest_on else "OFF",
            "head": "VISIBLE" if self.head_visible else "NOT_VISIBLE",
            "last_update": self.last_update.isoformat(),
        }


class StateController:
    def __init__(self, min_log_interval: float = 1.0):
        self.workers: Dict[int, WorkerState] = {}
        self.min_log_interval = min_log_interval
        self.last_log_time = defaultdict(lambda: 0.0)
        self.next_worker_id = 1
        self.previous_violation_states = {}

    def _assign_worker_id(self, person_box: list) -> int:
        x_center = (person_box[0] + person_box[2]) / 2
        y_center = (person_box[1] + person_box[3]) / 2
        min_distance = float("inf")
        closest_worker_id = None
        for worker_id, worker in self.workers.items():
            time_since_update = (datetime.now() - worker.last_update).total_seconds()
            if time_since_update < 2.0 and worker.last_position:
                dx = x_center - worker.last_position[0]
                dy = y_center - worker.last_position[1]
                distance = (dx**2 + dy**2) ** 0.5
                if distance < min_distance and distance < 200:
                    min_distance = distance
                    closest_worker_id = worker_id
        if closest_worker_id is not None:
            return closest_worker_id
        new_id = self.next_worker_id
        self.next_worker_id += 1
        return new_id

    def process_detections(self, detections: list) -> List[dict]:
        current_time = time.time()
        logs = []

        def is_class(det: dict, canonical: str, fallback_id: int) -> bool:
            return det.get("canonical_class") == canonical or det.get("class_id") == fallback_id

        person_detections = [d for d in detections if is_class(d, "person", 3)]
        helmet_detections = [d for d in detections if is_class(d, "helmet", 0)]
        vest_detections = [d for d in detections if is_class(d, "vest", 1)]
        head_detections = [d for d in detections if is_class(d, "head", 2)]

        for person_det in person_detections:
            person_box = person_det["box"]
            track_id = person_det.get("track_id")
            worker_id = track_id if track_id is not None else self._assign_worker_id(person_box)
            helmet_detected = self._check_overlap(person_box, helmet_detections)
            vest_detected = self._check_overlap(person_box, vest_detections)
            head_detected = self._check_overlap(person_box, head_detections)
            x_center = (person_box[0] + person_box[2]) / 2
            y_center = (person_box[1] + person_box[3]) / 2
            position = [x_center, y_center]
            is_new_worker = worker_id not in self.workers
            if is_new_worker:
                self.workers[worker_id] = WorkerState(worker_id, position)
            worker = self.workers[worker_id]
            previous_head_visible = worker.head_visible
            previous_vest_on = worker.vest_on
            prev_violations = self.previous_violation_states.get(worker_id, {"head_violation": False, "vest_violation": False})
            helmet_changed, vest_changed = worker.update(helmet_detected, vest_detected, position)
            worker.head_visible = head_detected
            head_changed = previous_head_visible != head_detected
            head_violation_started = (head_detected and not previous_head_visible) or (is_new_worker and head_detected)
            vest_violation_started = (not vest_detected and previous_vest_on) or (is_new_worker and not vest_detected)
            self.previous_violation_states[worker_id] = {"head_violation": head_detected, "vest_violation": not vest_detected}
            should_log = is_new_worker or ((helmet_changed or vest_changed or head_changed) and (current_time - self.last_log_time[worker_id]) >= self.min_log_interval)
            if should_log:
                self.last_log_time[worker_id] = current_time
                status = worker.get_status()
                violations = []
                if head_violation_started and not prev_violations.get("head_violation", False):
                    violations.append("head")
                if vest_violation_started and not prev_violations.get("vest_violation", False):
                    violations.append("vest")
                logs.append({"timestamp": datetime.now().isoformat(), "worker_id": worker_id, "changes": [], "status": status, "violations": violations})

        self._cleanup_old_workers()
        return logs

    def _check_overlap(self, person_box: list, detection_list: list, iou_threshold: float = 0.3) -> bool:
        return any(self._calculate_iou(person_box, det["box"]) > iou_threshold for det in detection_list)

    def _calculate_iou(self, box1: list, box2: list) -> float:
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
        return inter_area / union_area if union_area else 0.0

    def _cleanup_old_workers(self, max_age_seconds: float = 5.0):
        current_time = datetime.now()
        remove = []
        for worker_id, worker in list(self.workers.items()):
            age = (current_time - worker.last_update).total_seconds()
            if age > max_age_seconds:
                remove.append(worker_id)
        for wid in remove:
            self.workers.pop(wid, None)
            self.last_log_time.pop(wid, None)
            self.previous_violation_states.pop(wid, None)
