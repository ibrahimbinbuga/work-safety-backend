import os
import threading
import time
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
from ultralytics import YOLO

from app.workers.yolo.logic import StateController

_MODEL_CACHE = {}
_MODEL_LOCK = threading.Lock()
_frame_storage = {}
_frame_storage_lock = threading.Lock()


def _resolve_model_path(model_path: str) -> str:
    if not model_path:
        raise FileNotFoundError("Empty model path")
    if os.path.exists(model_path):
        return os.path.abspath(model_path)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # backend/app/workers -> project root is four levels up
    project_root = os.path.normpath(os.path.join(base_dir, "..", "..", ".."))

    # 1) Try path relative to project root (DB stores paths like model/weights/best.pt)
    project_relative = os.path.normpath(os.path.join(project_root, model_path))
    if os.path.exists(project_relative):
        return project_relative

    # 2) Fallback by filename in common model dirs
    file_name = os.path.basename(model_path)
    candidate_paths = [
        os.path.join(project_root, "model", "weights", file_name),
        os.path.join(project_root, "fall_model", "weights", file_name),
    ]
    for candidate in candidate_paths:
        normalized = os.path.normpath(candidate)
        if os.path.exists(normalized):
            return normalized
    raise FileNotFoundError(f"Model file not found: {model_path}")


def get_model(model_path: str):
    with _MODEL_LOCK:
        if model_path not in _MODEL_CACHE:
            resolved = _resolve_model_path(model_path)
            _MODEL_CACHE[model_path] = YOLO(resolved)
        return _MODEL_CACHE[model_path]


def preload_model_async(model_path: str):
    if model_path in _MODEL_CACHE:
        return True

    def _load():
        try:
            get_model(model_path)
        except Exception:
            pass

    threading.Thread(target=_load, daemon=True).start()
    return False


def _normalize_model_paths(model_paths) -> list[str]:
    if model_paths is None:
        return []
    if isinstance(model_paths, str):
        return [model_paths] if model_paths else []
    return [path for path in model_paths if path]


def _create_capture(source):
    if isinstance(source, str) and source.isdigit():
        source = int(source)
    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def _draw_status_overlay(frame, loaded_models_count: int, detections_count: int):
    annotated = frame.copy()
    status_text = f"Models: {loaded_models_count} | Detections: {detections_count}"
    cv2.rectangle(annotated, (8, 8), (300, 34), (0, 0, 0), -1)
    cv2.putText(annotated, status_text, (14, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return annotated


def run_camera_thread(camera_id: int, rtsp_url: str, model_paths, loop, violation_queue, stop_event: threading.Event, debug: bool = False, violation_check_interval: float = 600.0):
    state_controller = StateController(min_log_interval=1.0)
    source = 0 if rtsp_url in ("", None, "0") else rtsp_url
    normalized_model_paths = _normalize_model_paths(model_paths)
    loaded_models = []
    for model_path in normalized_model_paths:
        try:
            loaded_models.append((model_path, get_model(model_path)))
        except Exception:
            pass

    cap = _create_capture(source)
    frame_count = 0
    detections = []
    last_violation_check_time = time.time()

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.1)
            continue
        frame_count += 1

        if loaded_models and frame_count % 5 == 1:
            detections = []
            for _, model in loaded_models:
                try:
                    results = model.predict(frame, conf=0.1, verbose=False, device="cpu")
                    if results and results[0].boxes is not None:
                        for box in results[0].boxes:
                            detections.append(
                                {
                                    "class_id": int(box.cls[0]),
                                    "confidence": float(box.conf[0]) if box.conf is not None else 0.0,
                                    "box": box.xyxy[0].tolist(),
                                    "canonical_class": None,
                                }
                            )
                except Exception:
                    continue

        annotated = _draw_status_overlay(frame, len(loaded_models), len(detections))
        success, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if success:
            with _frame_storage_lock:
                _frame_storage[camera_id] = buffer.tobytes()

        current_time = time.time()
        if current_time - last_violation_check_time >= violation_check_interval:
            last_violation_check_time = current_time
            logs = state_controller.process_detections(detections)
            for log_entry in logs:
                violations = log_entry.get("violations", [])
                if violations:
                    payload = {
                        "camera_id": camera_id,
                        "camera_source": source,
                        "worker_id": log_entry.get("worker_id"),
                        "timestamp": log_entry.get("timestamp", datetime.now()),
                        "violations": violations,
                        "status": log_entry.get("status"),
                        "changes": log_entry.get("changes"),
                        "snapshot_path": None,
                    }
                    try:
                        loop.call_soon_threadsafe(violation_queue.put_nowait, payload)
                    except Exception:
                        pass
        time.sleep(0.02)

    cap.release()
    with _frame_storage_lock:
        _frame_storage.pop(camera_id, None)


def get_latest_frame(camera_id: int) -> Optional[bytes]:
    with _frame_storage_lock:
        return _frame_storage.get(camera_id)
