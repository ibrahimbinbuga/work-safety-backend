# backend/state_control.py
from typing import Dict, Tuple, List
from datetime import datetime
from collections import defaultdict
import time

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
            'worker_id': self.worker_id,
            'helmet': 'ON' if self.helmet_on else 'OFF',
            'vest': 'ON' if self.vest_on else 'OFF',
            'head': 'VISIBLE' if self.head_visible else 'NOT_VISIBLE',
            'last_update': self.last_update.isoformat()
        }


class StateController:
    """
    Lightweight state controller suitable for running in camera threads.
    Does NOT write to DB directly. Instead it returns logs including 'violations' started.
    """
    def __init__(self, min_log_interval: float = 1.0):
        self.workers: Dict[int, WorkerState] = {}
        self.min_log_interval = min_log_interval
        self.last_log_time = defaultdict(lambda: 0.0)
        self.next_worker_id = 1
        self.previous_violation_states = {}

    def _assign_worker_id(self, person_box: list) -> int:
        x_center = (person_box[0] + person_box[2]) / 2
        y_center = (person_box[1] + person_box[3]) / 2
        current_position = [x_center, y_center]

        min_distance = float('inf')
        closest_worker_id = None

        for worker_id, worker in self.workers.items():
            time_since_update = (datetime.now() - worker.last_update).total_seconds()
            if time_since_update < 2.0 and worker.last_position:
                dx = x_center - worker.last_position[0]
                dy = y_center - worker.last_position[1]
                distance = (dx**2 + dy**2)**0.5
                if distance < min_distance and distance < 200:
                    min_distance = distance
                    closest_worker_id = worker_id

        if closest_worker_id is not None:
            return closest_worker_id

        new_id = self.next_worker_id
        self.next_worker_id += 1
        return new_id

    def process_detections(self, detections: list) -> List[dict]:
        """
        Args:
            detections: list of detections, each: {'class_id':int,'confidence':float,'box':[x1,y1,x2,y2],'track_id':int|None}
        Returns:
            logs: list of dicts with keys:
              - timestamp, worker_id, changes (list), status (dict), violations (list of strings newly started)
        """
        current_time = time.time()
        logs = []

        person_detections = [d for d in detections if d['class_id'] == 3]
        helmet_detections = [d for d in detections if d['class_id'] == 0]
        vest_detections = [d for d in detections if d['class_id'] == 1]
        head_detections = [d for d in detections if d['class_id'] == 2]

        # process standalone heads (without person) as virtual workers
        head_detections_without_person = []
        for head_det in head_detections:
            head_box = head_det['box']
            associated = False
            for p in person_detections:
                if self._calculate_iou(p['box'], head_box) > 0.3:
                    associated = True
                    break
            if not associated:
                x_center = (head_box[0] + head_box[2]) / 2
                y_center = (head_box[1] + head_box[3]) / 2
                head_position = [x_center, y_center]
                head_id = None
                for wid, w in self.workers.items():
                    if w.last_position:
                        dx = x_center - w.last_position[0]
                        dy = y_center - w.last_position[1]
                        dist = (dx**2 + dy**2)**0.5
                        if dist < 200 and (datetime.now() - w.last_update).total_seconds() < 2.0:
                            head_id = wid
                            break
                if head_id is None:
                    head_id = self.next_worker_id
                    self.next_worker_id += 1
                head_detections_without_person.append({'head_det': head_det, 'head_id': head_id, 'position': head_position})

        # process persons
        for person_det in person_detections:
            person_box = person_det['box']
            track_id = person_det.get('track_id')
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
            previous_helmet_on = worker.helmet_on

            prev_violations = self.previous_violation_states.get(worker_id, {'head_violation': False, 'vest_violation': False})

            helmet_changed, vest_changed = worker.update(helmet_detected, vest_detected, position)
            worker.head_visible = head_detected
            head_changed = (previous_head_visible != head_detected)

            head_violation_started = (head_detected and not previous_head_visible) or (is_new_worker and head_detected)
            vest_violation_started = (not vest_detected and previous_vest_on) or (is_new_worker and not vest_detected)

            # Update violation state map
            self.previous_violation_states[worker_id] = {
                'head_violation': head_detected,
                'vest_violation': not vest_detected
            }

            # Decide if we should log
            should_log = False
            if is_new_worker:
                should_log = True
                self.last_log_time[worker_id] = current_time
            elif helmet_changed or vest_changed or head_changed:
                if (current_time - self.last_log_time[worker_id]) >= self.min_log_interval:
                    should_log = True
                    self.last_log_time[worker_id] = current_time

            if should_log:
                status = worker.get_status()
                change_messages = []
                if is_new_worker:
                    change_messages.append(f"Worker detected - Helmet: {status['helmet']}, Vest: {status['vest']}, Head: {status['head']}")
                else:
                    if helmet_changed:
                        change_messages.append(f"Helmet: {status['helmet']}")
                    if vest_changed:
                        change_messages.append(f"Vest: {status['vest']}")
                    if head_changed:
                        change_messages.append(f"Head: {status['head']}")

                violations = []
                if head_violation_started and not prev_violations.get('head_violation', False):
                    violations.append('head')
                if vest_violation_started and not prev_violations.get('vest_violation', False):
                    violations.append('vest')

                logs.append({
                    'timestamp': datetime.now().isoformat(),
                    'worker_id': worker_id,
                    'changes': change_messages,
                    'status': status,
                    'violations': violations,
                })

        # handle head detections without person -> treat as violation logs
        for head_info in head_detections_without_person:
            head_id = head_info['head_id']
            head_position = head_info['position']
            prev_violations = self.previous_violation_states.get(head_id, {'head_violation': False, 'vest_violation': False})

            if not prev_violations.get('head_violation', False):
                # create worker if not exists
                if head_id not in self.workers:
                    self.workers[head_id] = WorkerState(head_id, head_position)
                else:
                    self.workers[head_id].last_position = head_position
                    self.workers[head_id].last_update = datetime.now()

                self.workers[head_id].head_visible = True
                self.previous_violation_states[head_id] = {'head_violation': True, 'vest_violation': False}
                logs.append({
                    'timestamp': datetime.now().isoformat(),
                    'worker_id': head_id,
                    'changes': [f"Head visible without person (possible violation)"],
                    'status': self.workers[head_id].get_status(),
                    'violations': ['head'],
                })

        # cleanup
        self._cleanup_old_workers()
        return logs

    def _check_overlap(self, person_box: list, detection_list: list, iou_threshold: float = 0.3) -> bool:
        for det in detection_list:
            det_box = det['box']
            if self._calculate_iou(person_box, det_box) > iou_threshold:
                return True
        return False

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
        if union_area == 0:
            return 0.0
        return inter_area / union_area

    def _cleanup_old_workers(self, max_age_seconds: float = 5.0):
        from datetime import datetime
        current_time = datetime.now()
        remove = []
        for worker_id, worker in list(self.workers.items()):
            age = (current_time - worker.last_update).total_seconds()
            if age > max_age_seconds:
                remove.append(worker_id)
        for wid in remove:
            del self.workers[wid]
            if wid in self.last_log_time:
                del self.last_log_time[wid]
            if wid in self.previous_violation_states:
                del self.previous_violation_states[wid]
