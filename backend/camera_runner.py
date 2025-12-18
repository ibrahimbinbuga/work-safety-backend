# backend/camera_runner.py
import threading
import time
import os
import cv2
from ultralytics import YOLO
from state_control import StateController

# Model cache (yüklemeyi tekrar etmemek için global)
_MODEL_CACHE = {}
_MODEL_LOCK = threading.Lock()

# Global frame storage for streaming (camera_id -> encoded_frame_bytes)
_frame_storage = {}
_frame_storage_lock = threading.Lock()

def get_model(model_path: str):
    # Thread-safe model loading and caching
    global _MODEL_CACHE
    with _MODEL_LOCK:
        if model_path not in _MODEL_CACHE:
            try:
                print(f"[get_model] Loading model from {model_path}")
                model = YOLO(model_path)
                # Try to disable fuse to avoid 'bn' attribute error with older models
                try:
                    # Check if model has fuse method and try to work around it
                    if hasattr(model.model, 'fuse'):
                        print(f"[get_model] Model fuse method found, but will skip auto-fuse in predict")
                except:
                    pass
                _MODEL_CACHE[model_path] = model
                print(f"[get_model] Model loaded successfully")
            except Exception as e:
                print(f"[get_model] Error loading model from {model_path}: {e}")
                import traceback
                traceback.print_exc()
                print(f"[get_model] Trying fallback model: yolo11n.pt")

                
                try:  # It is used to load the yolo11n.pt model if the model is not found in the workspace
                    _MODEL_CACHE[model_path] = YOLO("yolo11n.pt")
                    print(f"[get_model] Fallback model loaded successfully")
                except Exception as e2:
                    print(f"[get_model] Fallback model also failed: {e2}")
                    raise
        return _MODEL_CACHE[model_path]

def run_camera_thread(camera_id: int, rtsp_url: str, model_path: str, loop, violation_queue, stop_event: threading.Event, debug: bool = False):
    """
    Blocking function intended to run in a separate thread.
    - loop: asyncio loop from the main app
    - violation_queue: asyncio.Queue to put violation dicts (use loop.call_soon_threadsafe)
    - stop_event: threading.Event used to stop the thread gracefully
    """
    state_controller = StateController(min_log_interval=1.0)

    # use rtsp_url or integer camera index
    source = rtsp_url
    if rtsp_url is None or rtsp_url == "":
        source = 0
    # If rtsp_url is "0" (string), convert to integer for local camera
    if rtsp_url == "0":
        source = 0

    print(f"[CameraRunner] Starting camera {camera_id} -> {source}")
    
    # Try to load model, if fails, continue without model (just show camera feed)
    try:
        model = get_model(model_path)
        use_model = True
    except Exception as e:
        print(f"[CameraRunner][Camera {camera_id}] Model loading failed: {e}")
        print(f"[CameraRunner][Camera {camera_id}] Continuing without model (raw camera feed only)")
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
                    print(f"[CameraRunner][Camera {camera_id}] RTSP stream not accessible (timeout or error), falling back to local camera (0)")
                    if test_error[0]:
                        print(f"[CameraRunner][Camera {camera_id}] RTSP error: {test_error[0]}")
                    source = 0  # Fallback to local camera
            
            # Open camera with OpenCV first, then run model.predict() on each frame
            # This avoids fuse() issues with model.track() or model.predict(stream=True)
            print(f"[CameraRunner][Camera {camera_id}] Opening camera with OpenCV for manual frame processing")
            source_cap = cv2.VideoCapture(source)
            if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
                source_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                source_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            source_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not source_cap.isOpened():
                print(f"[CameraRunner][Camera {camera_id}] Failed to open camera source: {source}")
                # Try to find available camera
                for i in range(5):
                    test_cap = cv2.VideoCapture(i)
                    if test_cap.isOpened():
                        ret, _ = test_cap.read()
                        if ret:
                            print(f"[CameraRunner][Camera {camera_id}] Found working camera at index {i}")
                            test_cap.release()
                            source_cap = cv2.VideoCapture(i)
                            source_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            source = i
                            break
                        test_cap.release()
                
                if not source_cap.isOpened():
                    print(f"[CameraRunner][Camera {camera_id}] No working camera found, exiting thread")
                    use_model = False
                    return
            
            print(f"[CameraRunner][Camera {camera_id}] Camera opened, starting detection loop")
            # We'll process frames manually in the loop below
            results = None
            cap = source_cap
        else:
            # Fallback: use OpenCV directly to capture frames without YOLO
            print(f"[CameraRunner][Camera {camera_id}] Opening camera with OpenCV, source: {source} (type: {type(source)})")
            cap = cv2.VideoCapture(source)
            if isinstance(source, str) and source.startswith('rtsp://'):
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for RTSP
            elif isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
                # Local camera - set properties
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not cap.isOpened():
                print(f"[CameraRunner][Camera {camera_id}] ERROR: Failed to open camera source: {source}")
                print(f"[CameraRunner][Camera {camera_id}] Trying to list available cameras...")
                # Try to find available camera
                for i in range(5):
                    test_cap = cv2.VideoCapture(i)
                    if test_cap.isOpened():
                        ret, _ = test_cap.read()
                        if ret:
                            print(f"[CameraRunner][Camera {camera_id}] Found working camera at index {i}")
                            test_cap.release()
                            cap = cv2.VideoCapture(i)
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            if cap.isOpened():
                                source = i
                                break
                        test_cap.release()
                
                if not cap.isOpened():
                    print(f"[CameraRunner][Camera {camera_id}] No working camera found, exiting thread")
                    return
            
            print(f"[CameraRunner][Camera {camera_id}] Camera opened successfully")
            results = None
        frame_count = 0
        # Violation check interval: check violations every 4 seconds
        VIOLATION_CHECK_INTERVAL = 4.0  # seconds
        last_violation_check_time = time.time()
        
        if use_model:
            # Use YOLO model with OpenCV frame capture - manual frame processing
            # This avoids fuse() issues that occur with model.track() or model.predict(stream=True)
            print(f"[CameraRunner][Camera {camera_id}] Starting detection loop with model (violation check interval: {VIOLATION_CHECK_INTERVAL}s)")
            consecutive_failures = 0
            while not stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures % 30 == 0:
                        print(f"[CameraRunner][Camera {camera_id}] Failed to read frame (consecutive: {consecutive_failures})")
                    time.sleep(0.1)
                    continue
                
                consecutive_failures = 0
                frame_count += 1
                
                # Run model prediction on the frame
                try:
                    # Use predict on single frame to avoid fuse() issues
                    pred_results = model.predict(frame, conf=0.25, verbose=False, device='cpu')
                    
                    if len(pred_results) == 0:
                        annotated_frame = frame
                        detections = []
                    else:
                        result = pred_results[0]
                        
                        # Get annotated frame with detections drawn
                        try:
                            annotated_frame = result.plot()  # YOLO automatically draws detections
                            # YOLO plot() returns RGB, convert to BGR for OpenCV
                            if len(annotated_frame.shape) == 3 and annotated_frame.shape[2] == 3:
                                annotated_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_RGB2BGR)
                        except Exception as plot_error:
                            print(f"[CameraRunner][Camera {camera_id}] Error plotting: {plot_error}")
                            annotated_frame = frame
                        
                        # Parse detections from result
                        detections = []
                        try:
                            if result.boxes is not None and len(result.boxes) > 0:
                                for box in result.boxes:
                                    try:
                                        if box.cls is None or box.xyxy is None:
                                            continue
                                        cls_id = int(box.cls[0])
                                        conf = float(box.conf[0]) if box.conf is not None else 0.0
                                        xyxy = box.xyxy[0].tolist()
                                        track_id = None  # No tracking ID with predict()
                                        detections.append({
                                            'class_id': cls_id,
                                            'confidence': conf,
                                            'box': xyxy,
                                            'track_id': track_id
                                        })
                                    except Exception as box_error:
                                        if debug:
                                            print(f"[CameraRunner][Camera {camera_id}] Error parsing single box: {box_error}")
                                        continue
                        except Exception as e:
                            if debug:
                                print(f"[CameraRunner][Camera {camera_id}] Error parsing boxes: {e}")
                except Exception as pred_error:
                    print(f"[CameraRunner][Camera {camera_id}] Error running prediction: {pred_error}")
                    annotated_frame = frame
                    detections = []
                
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
                    person_count = len([d for d in detections if d.get('class_id') == 3])
                    helmet_count = len([d for d in detections if d.get('class_id') == 0])
                    vest_count = len([d for d in detections if d.get('class_id') == 1])
                    head_count = len([d for d in detections if d.get('class_id') == 2])
                    print(f"[CameraRunner][Camera {camera_id}] Frame {frame_count} - Persons: {person_count}, Helmets: {helmet_count}, Vests: {vest_count}, Heads: {head_count}, Total: {len(detections)}")

                # Process detections through state controller - only check violations every 4 seconds
                current_time = time.time()
                if current_time - last_violation_check_time >= VIOLATION_CHECK_INTERVAL:
                    last_violation_check_time = current_time
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
                
                time.sleep(0.033)  # ~30 FPS
            
            print(f"[CameraRunner][Camera {camera_id}] Releasing camera...")
            cap.release()
        else:
            # Fallback: use OpenCV directly without YOLO
            print(f"[CameraRunner][Camera {camera_id}] Using OpenCV capture (no model)")
            consecutive_failures = 0
            while not stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures % 30 == 0:  # Log every 30 failures
                        print(f"[CameraRunner][Camera {camera_id}] Failed to read frame (consecutive failures: {consecutive_failures})")
                    time.sleep(0.1)
                    continue
                
                consecutive_failures = 0
                frame_count += 1
                
                # Encode frame as JPEG for streaming
                try:
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

