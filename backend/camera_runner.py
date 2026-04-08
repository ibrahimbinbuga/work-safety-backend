# backend/camera_runner.py
import threading
import time
import os
import cv2
import numpy as np
from typing import Optional
from ultralytics import YOLO

try:
    import requests
except ImportError:
    requests = None  # type: ignore
from state_control import StateController
from datetime import datetime


# Model cache (yüklemeyi tekrar etmemek için global)
_MODEL_CACHE = {}
_MODEL_LOCK = threading.Lock()


def _resolve_model_path(model_path: str) -> str:
    """Resolve model paths stored as project-root-relative or absolute paths.

    Paths stored in the DB are project-root-relative (e.g. 'model/weights/v1_best.pt')
    so the model can be found on any team member's machine regardless of where the
    project is cloned.
    """
    if not model_path:
        raise FileNotFoundError("Empty model path")

    if os.path.exists(model_path):
        return os.path.abspath(model_path)

    # backend/ is __file__'s directory; project root is one level up.
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(base_dir, '..'))

    # 1. Try as path relative to the project root (primary storage format).
    project_relative = os.path.normpath(os.path.join(project_root, model_path))
    if os.path.exists(project_relative):
        print(f"[_resolve_model_path] Resolved via project root: {model_path} -> {project_relative}")
        return project_relative

    # 2. Try as path relative to backend/ dir.
    backend_relative = os.path.normpath(os.path.join(base_dir, model_path))
    if os.path.exists(backend_relative):
        print(f"[_resolve_model_path] Resolved via backend dir: {model_path} -> {backend_relative}")
        return backend_relative

    # 3. Search common weight directories by filename as fallback.
    file_name = os.path.basename(model_path)
    candidate_paths = [
        os.path.join(project_root, 'model', 'weights', file_name),
        os.path.join(project_root, 'fall_model', 'weights', file_name),
    ]
    for candidate in candidate_paths:
        normalized = os.path.normpath(candidate)
        if os.path.exists(normalized):
            print(f"[_resolve_model_path] Resolved via filename search: {model_path} -> {normalized}")
            return normalized

    raise FileNotFoundError(
        f"Model file not found: '{model_path}'. "
        f"Expected a project-root-relative path like 'model/weights/best.pt'."
    )

# Global frame storage for streaming (camera_id -> encoded_frame_bytes)
_frame_storage = {}
_frame_storage_lock = threading.Lock()
MAX_CONSECUTIVE_READ_FAILURES = 30


def _is_rtsp_source(source) -> bool:
    return isinstance(source, str) and source.startswith('rtsp://')


def _is_http_source(source) -> bool:
    if not isinstance(source, str):
        return False
    s = source.strip().lower()
    return s.startswith('http://') or s.startswith('https://')


def _is_network_stream(source) -> bool:
    """RTSP or HTTP(S) — may need reconnect when reads fail."""
    return _is_rtsp_source(source) or _is_http_source(source)


def _is_local_source(source) -> bool:
    return isinstance(source, int) or (isinstance(source, str) and source.isdigit())


class HttpMjpegCapture:
    """
    Many phone / IP camera apps expose MJPEG over HTTP that works in a browser but
    fails with cv2.VideoCapture (FFmpeg). This reader streams the URL with requests,
    extracts JPEG frames (0xFFD8 … 0xFFD9), and decodes with cv2.imdecode.
    """

    def __init__(self, url: str):
        self.url = url.strip()
        self._lock = threading.Lock()
        self._latest = None
        self._stop = threading.Event()
        self._fatal = False
        self._thread = threading.Thread(target=self._run, name=f"HttpMjpeg-{id(self)}", daemon=True)
        self._thread.start()
        # Wait briefly for first frame so isOpened / open checks behave
        t0 = time.time()
        while time.time() - t0 < 20.0:
            with self._lock:
                if self._latest is not None:
                    break
            if self._fatal:
                break
            if not self._thread.is_alive():
                break
            time.sleep(0.05)

    def _run(self):
        if requests is None:
            print("[HttpMjpegCapture] requests not installed; pip install requests")
            self._fatal = True
            return
        buf = b""
        try:
            with requests.get(
                self.url,
                stream=True,
                timeout=(15, 120),
                headers={"User-Agent": "Mozilla/5.0 (compatible; SafetyWatch/1.0)"},
            ) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    if self._stop.is_set():
                        break
                    if not chunk:
                        continue
                    buf += chunk
                    if len(buf) > 4 * 1024 * 1024:
                        buf = buf[-2 * 1024 * 1024 :]
                    while True:
                        start = buf.find(b"\xff\xd8")
                        if start == -1:
                            break
                        end = buf.find(b"\xff\xd9", start + 2)
                        if end == -1:
                            buf = buf[start:]
                            break
                        jpg = buf[start : end + 2]
                        buf = buf[end + 2 :]
                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None and frame.size > 0:
                            with self._lock:
                                self._latest = frame
        except Exception as e:
            print(f"[HttpMjpegCapture] stream error for {self.url!r}: {e}")
            self._fatal = True

    def read(self):
        try:
            with self._lock:
                if self._latest is not None:
                    return True, self._latest.copy()
        except Exception as e:
            print(f"[HttpMjpegCapture] read error: {e}")
        return False, None

    def isOpened(self):
        if self._fatal:
            return False
        return self._thread.is_alive()

    def release(self):
        self._stop.set()
        self._thread.join(timeout=5.0)


def _create_capture_http(url: str):
    """
    HTTP/MJPEG IP cameras: default OpenCV backend often fails on Windows.
    Try CAP_FFMPEG first, then CAP_ANY, then default. Warm-up reads help MJPEG.
    """
    url = url.strip()
    candidates = []
    if hasattr(cv2, 'CAP_FFMPEG'):
        candidates.append((cv2.CAP_FFMPEG, 'CAP_FFMPEG'))
    if hasattr(cv2, 'CAP_ANY'):
        candidates.append((cv2.CAP_ANY, 'CAP_ANY'))
    candidates.append((None, 'default'))

    for backend, name in candidates:
        cap = None
        try:
            if backend is not None:
                cap = cv2.VideoCapture(url, backend)
            else:
                cap = cv2.VideoCapture(url)
            if not cap.isOpened():
                if cap:
                    cap.release()
                continue
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            try:
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 15000)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 15000)
            except Exception:
                pass
            # MJPEG over HTTP often needs several reads before a valid frame
            for attempt in range(30):
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    print(f"[_create_capture] HTTP stream OK ({name}), frame after {attempt + 1} read(s)")
                    return cap
            print(f"[_create_capture] HTTP opened ({name}) but no frame yet; main loop will retry")
            return cap
        except Exception as e:
            print(f"[_create_capture] HTTP open failed ({name}): {e}")
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
    return None


def _create_capture(source):
    # HTTP / HTTPS — prefer requests+JPEG parse (phone IP cameras); then OpenCV FFmpeg
    if _is_http_source(source):
        url = str(source).strip()
        if requests is not None:
            try:
                cap_mj = HttpMjpegCapture(url)
                if cap_mj.isOpened():
                    ok, frm = cap_mj.read()
                    if ok and frm is not None:
                        print(f"[_create_capture] HTTP MJPEG via requests+JPEG parse OK: {url[:80]}...")
                        return cap_mj
                    # Thread alive but no frame yet — still use (main loop will read)
                    print(f"[_create_capture] HTTP MJPEG reader running, waiting for frames: {url[:80]}...")
                    return cap_mj
                cap_mj.release()
            except Exception as e:
                print(f"[_create_capture] HttpMjpegCapture failed, trying OpenCV: {e}")
        cap = _create_capture_http(url)
        if cap is not None:
            return cap
        return cv2.VideoCapture(url)

    # On Windows, MSMF often emits grabFrame warnings for local webcams.
    # Prefer DirectShow for local camera indices and fallback to default backend.
    if _is_local_source(source):
        try:
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(source)
        except Exception:
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if _is_local_source(source):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # These options are backend-dependent; ignore silently when unsupported.
    try:
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
    except Exception:
        pass

    return cap


def _safe_read_frame(cap):
    """Read a frame without letting OpenCV C++ exceptions kill the camera thread."""
    try:
        return cap.read()
    except Exception as error:
        print(f"[CameraRunner] OpenCV read failed: {error}")
        return False, None

def get_model(model_path: str):
    # Thread-safe model loading and caching (non-blocking after first load)
    global _MODEL_CACHE
    with _MODEL_LOCK:
        if model_path not in _MODEL_CACHE:
            try:
                resolved_model_path = _resolve_model_path(model_path)
                print(f"[get_model] Loading model from {resolved_model_path}")
                model = YOLO(resolved_model_path)
                # Try to disable fuse to avoid 'bn' attribute error with older models
                try:
                    # Check if model has fuse method and try to work around it
                    if hasattr(model.model, 'fuse'):
                        print(f"[get_model] Model fuse method found, but will skip auto-fuse in predict")
                except:
                    pass
                _MODEL_CACHE[model_path] = model
                print(f"[get_model] ✅ Model loaded successfully: {resolved_model_path}")
            except Exception as e:
                print(f"[get_model] Error loading model from {model_path}: {e}")
                import traceback
                traceback.print_exc()
                # Do not silently fallback to default YOLO model.
                # If a custom model cannot be loaded, caller should skip it.
                raise
        return _MODEL_CACHE[model_path]

def preload_model_async(model_path: str):
    """
    Non-blocking model preload in background.
    Returns True if model is already cached, False if loading started.
    """
    global _MODEL_CACHE
    
    # Quick check without lock
    if model_path in _MODEL_CACHE:
        print(f"[preload_model_async] Model already cached: {model_path}")
        return True
    
    # Start loading in background thread
    def load_in_background():
        try:
            get_model(model_path)
        except Exception as e:
            print(f"[preload_model_async] Background loading failed: {e}")
    
    bg_thread = threading.Thread(target=load_in_background, daemon=True)
    bg_thread.start()
    print(f"[preload_model_async] Background model loading started for: {model_path}")
    return False


def _normalize_model_paths(model_paths) -> list[str]:
    if model_paths is None:
        return []
    if isinstance(model_paths, str):
        return [model_paths] if model_paths else []
    return [path for path in model_paths if path]


def _build_detection_entry(model_path: str, model_name: str, box, class_names) -> Optional[dict]:
    if box.cls is None or box.xyxy is None:
        return None

    cls_id = int(box.cls[0])
    if isinstance(class_names, dict):
        class_name = class_names.get(cls_id, str(cls_id))
    elif isinstance(class_names, (list, tuple)) and cls_id < len(class_names):
        class_name = class_names[cls_id]
    else:
        class_name = str(cls_id)

    class_name_text = str(class_name)
    class_key = class_name_text.strip().lower()
    canonical_map = {
        'person': 'person',
        'worker': 'person',
        'human': 'person',
        'insan': 'person',
        'helmet': 'helmet',
        'hardhat': 'helmet',
        'baret': 'helmet',
        'kask': 'helmet',
        'vest': 'vest',
        'yelek': 'vest',
        'head': 'head',
        'kafa': 'head',

        'fallen': 'fallen',
        'fall': 'fallen',
        'sitting': 'sitting',
        'standing': 'standing',
    }
    canonical_class = canonical_map.get(class_key)

    return {
        'model_path': model_path,
        'model_name': model_name,
        'class_id': cls_id,
        'class_name': class_name_text,
        'canonical_class': canonical_class,
        'confidence': float(box.conf[0]) if box.conf is not None else 0.0,
        'box': box.xyxy[0].tolist(),
        'track_id': None,
    }


def _run_multi_model_prediction(camera_id: int, frame, loaded_models, debug: bool = False):
    detections = []

    for model_path, model in loaded_models:
        try:
            pred_results = model.predict(frame, conf=0.1, verbose=False, device='cpu')
        except Exception as pred_error:
            print(f"[CameraRunner][Camera {camera_id}] Error running prediction for {model_path}: {pred_error}")
            continue

        if not pred_results:
            continue

        result = pred_results[0]
        class_names = getattr(model, 'names', {}) or {}
        model_name = os.path.basename(model_path)

        try:
            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    try:
                        entry = _build_detection_entry(model_path, model_name, box, class_names)
                        if entry:
                            detections.append(entry)
                    except Exception as box_error:
                        if debug:
                            print(f"[CameraRunner][Camera {camera_id}] Error parsing single box for {model_name}: {box_error}")
                        continue
        except Exception as parse_error:
            if debug:
                print(f"[CameraRunner][Camera {camera_id}] Error parsing boxes for {model_name}: {parse_error}")

    return detections


def _draw_combined_detections(frame, detections):
    annotated_frame = frame.copy()
    palette = [
        (64, 180, 255),
        (71, 99, 255),
        (60, 179, 113),
        (255, 191, 0),
        (255, 99, 71),
        (186, 85, 211),
    ]
    color_map = {}
    anchor_label_count = {}
    class_aliases = {
        'head': 'head',
        'helmet': 'helmet',
        'hardhat': 'helmet',
        'baret': 'helmet',
        'vest': 'vest',
        'yelek': 'vest',
        'person': 'person',
        'worker': 'person',
    }

    for detection in detections:
        xyxy = detection.get('box')
        if not xyxy or len(xyxy) != 4:
            continue

        model_name = detection.get('model_name', 'model')
        class_name = detection.get('class_name', str(detection.get('class_id', 'obj')))
        confidence = detection.get('confidence', 0.0)

        if model_name not in color_map:
            color_map[model_name] = palette[len(color_map) % len(palette)]
        color = color_map[model_name]

        x1, y1, x2, y2 = [int(coord) for coord in xyxy]
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1

        # Keep coordinates inside frame bounds.
        h, w = annotated_frame.shape[:2]
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w - 1))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h - 1))
        if x2 <= x1 or y2 <= y1:
            continue

        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)

        class_key = str(class_name).strip().lower()
        normalized_class_name = class_aliases.get(class_key, class_name)
        label = f"{normalized_class_name} {confidence:.2f}"

        # Avoid stacked/overlapping labels when multiple models detect same area.
        anchor = (x1 // 20, y1 // 20)
        overlap_index = anchor_label_count.get(anchor, 0)
        anchor_label_count[anchor] = overlap_index + 1
        label_y = max(18, y1 - 8 + (overlap_index * 18))

        # Draw a filled background for better readability.
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        bg_x1 = x1
        bg_y2 = label_y + baseline + 2
        bg_y1 = max(0, label_y - text_h - 4)
        bg_x2 = min(w - 1, bg_x1 + text_w + 8)
        cv2.rectangle(annotated_frame, (bg_x1, bg_y1), (bg_x2, bg_y2), color, -1)
        cv2.putText(
            annotated_frame,
            label,
            (bg_x1 + 4, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    return annotated_frame


def _draw_status_overlay(frame, loaded_models_count: int, detections_count: int):
    """Render a stable status overlay so users always see runtime model/detection state."""
    annotated = frame.copy()
    status_text = f"Models: {loaded_models_count} | Detections: {detections_count}"
    cv2.rectangle(annotated, (8, 8), (300, 34), (0, 0, 0), -1)
    cv2.putText(
        annotated,
        status_text,
        (14, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return annotated

def run_camera_thread(camera_id: int, rtsp_url: str, model_paths, loop, violation_queue, stop_event: threading.Event, debug: bool = False, violation_check_interval: float = 600.0):
    """
    Blocking function intended to run in a separate thread.
    - loop: asyncio loop from the main app
    - violation_queue: asyncio.Queue to put violation dicts (use loop.call_soon_threadsafe)
    - stop_event: threading.Event used to stop the thread gracefully
    - violation_check_interval: saniye cinsinden detection kayıt sıklığı (priority'e göre belirlenir)
    """
    state_controller = StateController(min_log_interval=1.0)

    # use rtsp_url or integer camera index
    source = rtsp_url
    if rtsp_url is None or rtsp_url == "":
        source = 0
    # If rtsp_url is "0" (string), convert to integer for local camera
    if rtsp_url == "0":
        source = 0

    normalized_model_paths = _normalize_model_paths(model_paths)
    print(f"[CameraRunner] Starting camera {camera_id} -> {source} (models: {normalized_model_paths})")
    
    # Try to load model, if fails, continue without model (just show camera feed)
    # ⏳ Eğer model henüz yüklenmiyorsa, maksimum 15 saniye bekle (bloke etmez)
    model = None
    use_model = False
    
    loaded_models = []

    if normalized_model_paths:
        for model_path in normalized_model_paths:
            try:
                print(f"[CameraRunner][Camera {camera_id}] Model'i yüklüyoruz: {model_path}")
                loaded_models.append((model_path, get_model(model_path)))
                print(f"[CameraRunner][Camera {camera_id}] ✅ Model yüklendi: {model_path}")
            except Exception as e:
                print(f"[CameraRunner][Camera {camera_id}] Model loading failed for {model_path}: {e}")
        model = loaded_models[0][1] if loaded_models else None
        use_model = len(loaded_models) > 0
    else:
        print(f"[CameraRunner][Camera {camera_id}] Model disabled for this camera, running raw feed only")
        model = None
        use_model = False
    
    try:
        if use_model:
            # For RTSP streams, test connection first with timeout
            if isinstance(source, str) and source.startswith('rtsp://'):
                print(f"[CameraRunner][Camera {camera_id}] Testing RTSP connection: {source}")
                import threading
                test_success = [False]
                test_error = [None]
                
                def test_rtsp():
                    try:
                        test_cap = cv2.VideoCapture(source)
                        test_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        # Try to read a frame with timeout
                        ret, _ = test_cap.read()
                        test_cap.release()
                        test_success[0] = ret
                    except Exception as e:
                        test_error[0] = str(e)
                
                # Run test with 3 second timeout
                test_thread = threading.Thread(target=test_rtsp, daemon=True)
                test_thread.start()
                test_thread.join(timeout=3.0)
                
                if not test_success[0]:
                    print(f"[CameraRunner][Camera {camera_id}] RTSP stream not accessible (timeout or error). Will keep RTSP source and retry.")
                    if test_error[0]:
                        print(f"[CameraRunner][Camera {camera_id}] RTSP error: {test_error[0]}")
            
            # Open camera with OpenCV first, then run model.predict() on each frame
            # This avoids fuse() issues with model.track() or model.predict(stream=True)
            print(f"[CameraRunner][Camera {camera_id}] Opening camera with OpenCV for manual frame processing")
            source_cap = _create_capture(source)
            
            if not source_cap.isOpened():
                print(f"[CameraRunner][Camera {camera_id}] Failed to open camera source: {source}")
                if _is_network_stream(source):
                    print(f"[CameraRunner][Camera {camera_id}] Network stream: will retry in main loop (RTSP/HTTP).")
                else:
                    # Never fall back to laptop webcam when a non-network source fails
                    print(
                        f"[CameraRunner][Camera {camera_id}] Not falling back to local webcam — "
                        "fix rtsp_url or network."
                    )
                    return
            if source_cap.isOpened():
                print(f"[CameraRunner][Camera {camera_id}] Camera opened, starting detection loop")
            else:
                print(f"[CameraRunner][Camera {camera_id}] RTSP capture not open yet; main loop will reconnect.")
            # We'll process frames manually in the loop below
            results = None
            cap = source_cap
        else:
            # Fallback: use OpenCV directly to capture frames without YOLO
            print(f"[CameraRunner][Camera {camera_id}] Opening camera with OpenCV, source: {source} (type: {type(source)})")
            cap = _create_capture(source)
            
            if not cap.isOpened():
                print(f"[CameraRunner][Camera {camera_id}] ERROR: Failed to open camera source: {source}")
                if _is_network_stream(source):
                    print(f"[CameraRunner][Camera {camera_id}] Network stream: will retry in main loop (RTSP/HTTP).")
                else:
                    print(
                        f"[CameraRunner][Camera {camera_id}] Not falling back to local webcam — "
                        "fix rtsp_url or network."
                    )
                    return

            if cap.isOpened():
                print(f"[CameraRunner][Camera {camera_id}] Camera opened successfully")
            else:
                print(f"[CameraRunner][Camera {camera_id}] RTSP capture not open yet; main loop will reconnect.")
            results = None
        frame_count = 0
        detections = []  # last known detections, reused between inference frames
        # Violation check interval: priority'e göre belirlenir (critical=30s, high=120s, medium=600s, low=1800s)
        VIOLATION_CHECK_INTERVAL = violation_check_interval
        last_violation_check_time = time.time()
        # Run inference only every N frames to avoid freezing on CPU.
        # Between inference frames the last known detections are reused so
        # bounding boxes stay visible and the stream remains smooth.
        INFERENCE_EVERY_N_FRAMES = 5

        if use_model:
            # Use YOLO model with OpenCV frame capture - manual frame processing
            # This avoids fuse() issues that occur with model.track() or model.predict(stream=True)
            print(f"[CameraRunner][Camera {camera_id}] Starting detection loop with model (violation check interval: {VIOLATION_CHECK_INTERVAL}s)")
            consecutive_failures = 0
            reconnect_attempts = 0
            while not stop_event.is_set():
                ret, frame = _safe_read_frame(cap)
                if not ret:
                    if frame_count == 0:
                        print(f"[CameraRunner][Camera {camera_id}] ERROR: No frame received from camera!")
                    consecutive_failures += 1
                    if consecutive_failures % 30 == 0:
                        print(f"[CameraRunner][Camera {camera_id}] Failed to read frame (consecutive: {consecutive_failures})")

                    if _is_network_stream(source) and consecutive_failures >= MAX_CONSECUTIVE_READ_FAILURES:
                        reconnect_attempts += 1
                        backoff = min(5.0, float(reconnect_attempts))
                        kind = 'HTTP' if _is_http_source(source) else 'RTSP'
                        print(f"[CameraRunner][Camera {camera_id}] Reconnecting {kind} (attempt {reconnect_attempts}) in {backoff:.1f}s...")
                        try:
                            cap.release()
                        except Exception:
                            pass
                        time.sleep(backoff)
                        cap = _create_capture(source)
                        if cap.isOpened():
                            consecutive_failures = 0
                            reconnect_attempts = 0
                            print(f"[CameraRunner][Camera {camera_id}] {kind} reconnect successful")
                        else:
                            print(f"[CameraRunner][Camera {camera_id}] {kind} reconnect failed")

                    time.sleep(0.1)
                    continue
                if frame_count == 0:
                    print(f"[CameraRunner][Camera {camera_id}] First frame received successfully!")
                
                consecutive_failures = 0
                reconnect_attempts = 0
                frame_count += 1

                # Run inference only on every Nth frame; reuse last detections otherwise.
                if frame_count % INFERENCE_EVERY_N_FRAMES == 1:
                    try:
                        detections = _run_multi_model_prediction(camera_id, frame, loaded_models, debug=debug)
                    except Exception as pred_error:
                        print(f"[CameraRunner][Camera {camera_id}] Error running prediction: {pred_error}")
                        detections = []
                # else: keep previous `detections` value

                try:
                    annotated_frame = _draw_combined_detections(frame, detections) if detections else frame
                    annotated_frame = _draw_status_overlay(annotated_frame, len(loaded_models), len(detections))
                except Exception as draw_error:
                    print(f"[CameraRunner][Camera {camera_id}] Error drawing detections: {draw_error}")
                    annotated_frame = _draw_status_overlay(frame, len(loaded_models), 0)
                
                # Encode frame as JPEG for streaming
                try:
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                    success, buffer = cv2.imencode('.jpg', annotated_frame, encode_param)
                    
                    if success:
                        frame_bytes = buffer.tobytes()
                        # Store frame in global storage (thread-safe)
                        with _frame_storage_lock:
                            _frame_storage[camera_id] = frame_bytes
                        
                        # Log first successful frame
                        if frame_count == 1:
                            print(f"[CameraRunner][Camera {camera_id}] First frame processed! Detections: {len(detections)}")
                    else:
                        print(f"[CameraRunner][Camera {camera_id}] Failed to encode frame")
                except Exception as e:
                    print(f"[CameraRunner][Camera {camera_id}] Error encoding frame: {e}")
                
                # Debug: print detection counts periodically
                if frame_count % 150 == 0:
                    person_count = len([d for d in detections if d.get('canonical_class') == 'person'])
                    helmet_count = len([d for d in detections if d.get('canonical_class') == 'helmet'])
                    vest_count = len([d for d in detections if d.get('canonical_class') == 'vest'])
                    head_count = len([d for d in detections if d.get('canonical_class') == 'head'])
                    fallen_count = len([d for d in detections if d.get('canonical_class') == 'fallen'])
                    sitting_count = len([d for d in detections if d.get('canonical_class') == 'sitting'])
                    standing_count = len([d for d in detections if d.get('canonical_class') == 'standing'])
                    print(
                        f"[CameraRunner][Camera {camera_id}] Frame {frame_count} - "
                        f"Persons: {person_count}, Helmets: {helmet_count}, Vests: {vest_count}, Heads: {head_count}, Fallen: {fallen_count}, Sitting: {sitting_count}, Standing: {standing_count}, "
                        f"Total: {len(detections)}, Models: {len(loaded_models)}"
                    )

                # Process detections - only check violations every 20 seconds
                current_time = time.time()
                if current_time - last_violation_check_time >= VIOLATION_CHECK_INTERVAL:
                    last_violation_check_time = current_time

                    # Fall model: only 'fallen' is a real safety violation.
                    # 'sitting' and 'standing' are normal states — saving them every interval
                    # creates massive DB bloat without safety value.
                    is_fallen = any(
                        d.get('canonical_class') == 'fallen'
                        for d in detections
                    )
                    if is_fallen:
                        payload = {
                            'camera_id': camera_id,
                            'camera_source': source,
                            'worker_id': 0,
                            'timestamp': datetime.now(),
                            'violations': ['fallen'],
                            'status': 'posture_detected',
                            'changes': None,
                            'snapshot_path': None,
                        }
                        try:
                            loop.call_soon_threadsafe(violation_queue.put_nowait, payload)
                            print(f"[CameraRunner][Camera {camera_id}] fallen person detected — violation sent to queue")
                        except Exception as e:
                            print(f"[CameraRunner][Camera {camera_id}] error sending posture violation: {e}")

                    logs = state_controller.process_detections(detections)
                    if logs:
                        for log_entry in logs:
                            # If violations list is not empty, send to async queue for DB write
                            violations = log_entry.get('violations', [])
                            if violations:
                                print(f"[CameraRunner][Camera {camera_id}] ⚠️ VIOLATION DETECTED! Worker {log_entry.get('worker_id')}: {violations}")
                                payload = {
                                    'camera_id': camera_id,
                                    'camera_source': source,
                                    'worker_id': log_entry.get('worker_id'),
                                    'timestamp': log_entry.get('timestamp'),
                                    'violations': violations,
                                    'status': log_entry.get('status'),
                                    'changes': log_entry.get('changes'),
                                    'snapshot_path': None
                                }
                                # Put into asyncio queue in a thread-safe way
                                try:
                                    loop.call_soon_threadsafe(violation_queue.put_nowait, payload)
                                    print(f"[CameraRunner][Camera {camera_id}] ✅ Violation sent to queue")
                                except Exception as queue_error:
                                    print(f"[CameraRunner][Camera {camera_id}] ❌ Error sending violation to queue: {queue_error}")

                # Small sleep to yield CPU between frames; inference itself provides natural pacing.
                time.sleep(0.01)

            print(f"[CameraRunner][Camera {camera_id}] Releasing camera...")
            cap.release()
        else:
            # Fallback: use OpenCV directly without YOLO
            print(f"[CameraRunner][Camera {camera_id}] Using OpenCV capture (no model)")
            consecutive_failures = 0
            reconnect_attempts = 0
            while not stop_event.is_set():
                ret, frame = _safe_read_frame(cap)
                if not ret:
                    if frame_count == 0:
                        print(f"[CameraRunner][Camera {camera_id}] ERROR: No frame received from camera (no model)!")
                    consecutive_failures += 1
                    if consecutive_failures % 30 == 0:  # Log every 30 failures
                        print(f"[CameraRunner][Camera {camera_id}] Failed to read frame (consecutive failures: {consecutive_failures})")

                    if _is_network_stream(source) and consecutive_failures >= MAX_CONSECUTIVE_READ_FAILURES:
                        reconnect_attempts += 1
                        backoff = min(5.0, float(reconnect_attempts))
                        kind = 'HTTP' if _is_http_source(source) else 'RTSP'
                        print(f"[CameraRunner][Camera {camera_id}] Reconnecting {kind} (no model, attempt {reconnect_attempts}) in {backoff:.1f}s...")
                        try:
                            cap.release()
                        except Exception:
                            pass
                        time.sleep(backoff)
                        cap = _create_capture(source)
                        if cap.isOpened():
                            consecutive_failures = 0
                            reconnect_attempts = 0
                            print(f"[CameraRunner][Camera {camera_id}] {kind} reconnect successful")
                        else:
                            print(f"[CameraRunner][Camera {camera_id}] {kind} reconnect failed")

                    time.sleep(0.1)
                    continue
                if frame_count == 0:
                    print(f"[CameraRunner][Camera {camera_id}] First frame received successfully! (no model)")
                
                consecutive_failures = 0
                reconnect_attempts = 0
                frame_count += 1
                
                # Encode frame as JPEG for streaming
                try:
                    frame = _draw_status_overlay(frame, 0, 0)
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                    success, buffer = cv2.imencode('.jpg', frame, encode_param)
                    
                    if success:
                        frame_bytes = buffer.tobytes()
                        # Store frame in global storage (thread-safe)
                        with _frame_storage_lock:
                            _frame_storage[camera_id] = frame_bytes
                        
                        # Log first successful frame
                        if frame_count == 1:
                            print(f"[CameraRunner][Camera {camera_id}] First frame encoded successfully! Size: {len(frame_bytes)} bytes")
                    else:
                        print(f"[CameraRunner][Camera {camera_id}] Failed to encode frame")
                except Exception as e:
                    print(f"[CameraRunner][Camera {camera_id}] Error encoding frame: {e}")
                    import traceback
                    traceback.print_exc()
                
                # optional debug print
                if debug and frame_count % 150 == 0:
                    print(f"[CameraRunner][Camera {camera_id}] Frame {frame_count} (no model)")
                
                time.sleep(0.033)  # ~30 FPS
            
            print(f"[CameraRunner][Camera {camera_id}] Releasing camera...")
            cap.release()

    except Exception as e:
        print(f"[CameraRunner][Camera {camera_id}] Exception: {e}")
    finally:
        # Clean up frame storage when camera stops
        with _frame_storage_lock:
            if camera_id in _frame_storage:
                del _frame_storage[camera_id]
        print(f"[CameraRunner] Camera {camera_id} stopped.")

def get_latest_frame(camera_id: int) -> bytes:
    """Get the latest encoded frame for a camera (thread-safe)."""
    with _frame_storage_lock:
        return _frame_storage.get(camera_id, None)
