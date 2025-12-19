# backend/main.py
import json
import base64
import shutil
import asyncio
import threading
import uuid
import cv2
import numpy as np
import os
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from database import engine, Base, AsyncSessionLocal, get_db
import models
from camera_runner import run_camera_thread, get_latest_frame
from sqlalchemy.ext.asyncio import AsyncSession
import time
from dotenv import load_dotenv
from ultralytics import YOLO

# Load environment variables
load_dotenv()

app = FastAPI()

# CORS (dev için geniş izin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global structures to manage camera threads and queue
camera_threads = {}  # camera_id -> {'thread': Thread, 'stop_event': Event}
violation_queue = None  # asyncio.Queue set at startup
consumer_task = None
main_loop = None

# Model path logic
backend_dir = Path(__file__).parent
weights_dir = backend_dir.parent / "model" / "weights"
config_file = weights_dir / "active_model.txt"

def get_initial_model_path():
    # 1. Env var
    env_path = os.getenv("MODEL_PATH")
    if env_path:
        return env_path
    
    # 2. Config file
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                saved_name = f.read().strip()
                saved_path = weights_dir / saved_name
                if saved_path.exists():
                    return str(saved_path)
        except Exception:
            pass

    # 3. Default fallback
    return str(weights_dir / "best.pt")

MODEL_PATH = get_initial_model_path()

@app.on_event("startup") # It is first function that is called when the application starts with FastAPI
async def startup_event():
    global violation_queue, consumer_task, main_loop
    print("[startup] Creating DB tables...")
    async with engine.begin() as conn:  # It is used to create the tables in the database if they don't exist
        await conn.run_sync(Base.metadata.create_all)

    # create queue and start consumer task
    main_loop = asyncio.get_running_loop()
    violation_queue = asyncio.Queue()

    consumer_task = asyncio.create_task(violation_consumer_task(violation_queue))

    # load cameras from DB and start threads
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(models.Camera))  # In models.py, we have defined the Camera class and the select statement is used to select the cameras from the database
        cameras = result.scalars().all()
        print(f"[startup] Found {len(cameras)} cameras in database")
        if not cameras:
            # insert sample cameras if none exist
            print("[startup] No cameras found, creating sample cameras...")
            cam1 = models.Camera(name="Warehouse A - Entry", location="Zone 1", rtsp_url="0", status="online")
            cam2 = models.Camera(name="Loading Dock", location="Zone 2", rtsp_url="", status="offline")
            session.add_all([cam1, cam2])
            await session.commit()
            cameras = [cam1, cam2]
            print(f"[startup] Created {len(cameras)} sample cameras")

    # Start a thread per camera that is online
    print(f"[startup] Checking cameras for startup...")
    online_count = 0
    for cam in cameras: 
        print(f"[startup] Camera {cam.id}: name={cam.name}, status={cam.status}, rtsp_url={cam.rtsp_url}")
        if cam.status == "online":
            print(f"[startup] Starting camera thread for camera {cam.id}...")
            start_camera_thread(cam.id, cam.rtsp_url)  # It is used to start the camera thread for each camera using the start_camera_thread function
            online_count += 1
        else:
            print(f"[startup] Skipping camera {cam.id} (status: {cam.status})")
    print(f"[startup] Started {online_count} camera thread(s)")

@app.on_event("shutdown") # It is the second function that is called when the application shuts down with FastAPI
async def shutdown_event():
    # stop camera threads
    for cam_id, info in list(camera_threads.items()): # It is used to stop the camera threads for each camera using the stop_camera_thread function
        print(f"[shutdown] stopping camera {cam_id}")
        info['stop_event'].set()
        info['thread'].join(timeout=5.0)
    # stop consumer+
    global consumer_task
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    print("[shutdown] Goodbye!")

def start_camera_thread(camera_id: int, rtsp_url: str):
    """Start a blocking camera loop in a separate thread."""
    if camera_id in camera_threads:  # It is used to check if the camera thread is already running
        print(f"[start_camera_thread] Camera {camera_id} already running")
        return
    
    if main_loop is None:  # It is used to check if the main loop is already running
        print(f"[start_camera_thread] ERROR: main_loop is None, cannot start camera {camera_id}")
        return
    
    if violation_queue is None:  # It is used to check if the violation queue is already running
        print(f"[start_camera_thread] ERROR: violation_queue is None, cannot start camera {camera_id}")
        return
    
    print(f"[start_camera_thread] Creating thread for camera {camera_id} with rtsp_url='{rtsp_url}'")
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_camera_thread,
        args=(camera_id, rtsp_url, MODEL_PATH, main_loop, violation_queue, stop_event),
        daemon=True
    )
    camera_threads[camera_id] = {'thread': thread, 'stop_event': stop_event}
    thread.start()
    print(f"[start_camera_thread] Started camera thread for {camera_id}")

async def violation_consumer_task(queue: asyncio.Queue):
    """
    Consumes violation payloads from the queue and writes to DB (async).
    """
    print("[consumer] Violation consumer started.")
    while True:
        payload = await queue.get()
        try:
            await save_violation_async(payload)
        except Exception as e:
            print(f"[consumer] Error saving violation: {e}")
        finally:
            queue.task_done()

async def save_violation_async(payload: dict):
    """
    Save the payload as Detection (and Violation) to DB using AsyncSession.
    Eski db_config.py'deki save_violation fonksiyonunun mantığına uygun olarak yazıldı.
    
    Args:
        payload: dict containing:
            - violations: list of violation types ('head' or 'vest')
            - camera_id: camera ID
            - worker_id: worker ID (used as violation_id)
            - snapshot_path: optional snapshot path
    """
    async with AsyncSessionLocal() as session:
        try:
            # Create Detection rows for each violation type (head/vest etc.)
            for v in payload.get('violations', []):
                # Validate violation type (eski kodun mantığına uygun)
                if v not in ['head', 'vest']:
                    print(f"[consumer] Invalid violation type: {v}, skipping...")
                    continue
                
                # Create Detection record
                det = models.Detection(  # In models.py, we have defined the Detection class and the add method is used to add the detection to the database
                    camera_id=payload.get('camera_id'),
                    detection_type=v,
                    confidence=None,
                    is_violation=True,
                    snapshot_path=payload.get('snapshot_path'),
                )
                session.add(det)

                # Create Violation record (eski db_config.py save_violation fonksiyonunun mantığına uygun)
                # violation_id: worker_id kullanılıyor (eski kodda parametre olarak alınıyordu: violation_id: int)
                # tarih_saat: otomatik olarak server_default=func.now() ile kaydedilecek (CURRENT_TIMESTAMP gibi)
                worker_id = payload.get('worker_id')
                if worker_id is None:
                    print(f"[consumer] ⚠️ Warning: worker_id is None for violation {v}, using 0 as default")
                    worker_id = 0
                
                violation_area = str(payload.get('camera_id')) if payload.get('camera_id') is not None else None  # ihlal_yapilan_bolge (optional, can be None)
                
                vio = models.Violation(  # In models.py, we have defined the Violation class and the add method is used to add the violation to the database
                    ihlal_cesidi=v,  # violation_type: 'head' or 'vest'
                    ihlal_yapilan_bolge=violation_area,  # violation_area: optional area where violation occurred
                    violation_id=int(worker_id)  # violation_id: The worker/violation ID (int, required - eski kodun mantığına uygun)
                )
                session.add(vio)

            await session.commit()
            print(f"[consumer] ✅ Saved violation(s) for camera {payload.get('camera_id')} - {payload.get('violations')}, worker_id={payload.get('worker_id')}")
        except Exception as e:
            await session.rollback()
            print(f"[consumer] ❌ Error saving violation: {e}")
            import traceback
            traceback.print_exc()
            raise

# Simple endpoints
@app.get("/")
async def root():
    return {"message": "SafetyWatch API running"}

@app.get("/api/cameras")
async def get_cameras(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Camera))
    return result.scalars().all()

@app.get("/api/detections")
async def get_detections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Detection))
    return result.scalars().all()

@app.get("/api/violations")
async def get_violations(db: AsyncSession = Depends(get_db)):
    """Get all violations from the database."""
    result = await db.execute(select(models.Violation).order_by(models.Violation.tarih_saat.desc()))
    violations = result.scalars().all()
    return violations

@app.post("/api/model/upload")
async def upload_model(
    file: UploadFile = File(...),
    version: str = Form(...),
    description: str = Form(None),
    accuracy: float = Form(0.0),
    helmet_precision: float = Form(0.0),
    vest_precision: float = Form(0.0),
    worker_recall: float = Form(0.0)
):
    try:
        # Ensure directory exists
        backend_dir = Path(__file__).parent
        weights_dir = backend_dir.parent / "model" / "weights"
        weights_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = weights_dir / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Save metadata
        metadata = {
            "version": version,
            "description": description,
            "metrics": {
                "accuracy": accuracy,
                "helmet_precision": helmet_precision,
                "vest_precision": vest_precision,
                "worker_recall": worker_recall
            },
            "upload_date": time.time()
        }
        
        meta_path = weights_dir / f"{file.filename}.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f)
            
        print(f"[upload] Model saved to {file_path} with metadata")
        return {"status": "success", "filename": file.filename, "path": str(file_path)}
    except Exception as e:
        print(f"[upload] Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/model/current")
async def get_current_model():
    """Get information about the currently active model."""
    path = Path(MODEL_PATH)
    exists = path.exists()
    
    # Default metrics
    metrics = {
        "accuracy": 0,
        "helmet_precision": 0,
        "vest_precision": 0,
        "worker_recall": 0
    }
    version_label = path.stem
    
    if exists:
        # Try to load metadata
        meta_path = path.parent / f"{path.name}.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r") as f:
                    data = json.load(f)
                    if "metrics" in data:
                        metrics = data["metrics"]
                    if "version" in data:
                        version_label = data["version"]
            except Exception as e:
                print(f"Error reading metadata: {e}")

    return {
        "version": version_label,
        "filename": path.name,
        "path": str(path),
        "size_mb": round(path.stat().st_size / (1024 * 1024), 2) if exists else 0,
        "status": "active" if exists else "missing",
        "last_modified": time.ctime(path.stat().st_mtime) if exists else None,
        "metrics": metrics
    }

@app.get("/api/model/history")
async def get_model_history():
    """List all model files in the weights directory."""
    backend_dir = Path(__file__).parent
    weights_dir = backend_dir.parent / "model" / "weights"
    history = []
    
    if weights_dir.exists():
        current_resolve = Path(MODEL_PATH).resolve() if Path(MODEL_PATH).exists() else None
        
        for f in weights_dir.glob("*.pt"):
            is_active = False
            if current_resolve and f.resolve() == current_resolve:
                is_active = True
                
            # Read metadata
            meta_path = f.parent / f"{f.name}.json"
            accuracy = 0
            version_label = f.stem
            
            if meta_path.exists():
                try:
                    with open(meta_path, "r") as jf:
                        data = json.load(jf)
                        metrics = data.get("metrics", {})
                        accuracy = metrics.get("accuracy", 0)
                        if "version" in data:
                            version_label = data["version"]
                except:
                    pass

            history.append({
                "version": version_label,
                "filename": f.name,
                "date": time.strftime("%Y-%m-%d", time.localtime(f.stat().st_mtime)),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "status": "active" if is_active else "archived",
                "accuracy": accuracy,
                "detections": 0 # Placeholder
            })
    
    # Sort by date desc
    history.sort(key=lambda x: x['date'], reverse=True)
    return history

@app.delete("/api/model/{filename}")
async def delete_model(filename: str):
    """Delete a model file if it is not currently active."""
    target_path = weights_dir / filename
    
    # Don't delete if it's the active model
    if str(target_path.resolve()) == str(Path(MODEL_PATH).resolve()):
        return {"status": "error", "message": "Cannot delete the currently active model"}
        
    if not target_path.exists():
        return {"status": "error", "message": "File not found"}
        
    try:
        os.remove(target_path)
        return {"status": "success", "filename": filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/model/test")
async def test_model_inference(file: UploadFile = File(...)):
    """Run inference on a single uploaded image for testing."""
    temp_path = f"temp_{uuid.uuid4()}.jpg"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        model = YOLO(MODEL_PATH)
        results = model(temp_path)
        
        # Count detections by class name
        summary = {}
        total_conf = 0
        count = 0
        
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                name = model.names[cls_id]
                
                summary[name] = summary.get(name, 0) + 1
                total_conf += conf
                count += 1
                
        avg_conf = (total_conf / count * 100) if count > 0 else 0

        # Generate visualization (draw boxes)
        im_array = results[0].plot() # Returns BGR numpy array
        _, img_encoded = cv2.imencode('.jpg', im_array)
        img_base64 = base64.b64encode(img_encoded).decode('utf-8')
        
        return {
            "success": True,
            "summary": summary,
            "confidence": round(avg_conf, 1),
            "image_base64": f"data:image/jpeg;base64,{img_base64}"
        }
    except Exception as e:
        print(f"Inference error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/api/model/activate")
async def activate_model(filename: str = Form(...)):
    global MODEL_PATH
    
    target_path = weights_dir / filename
    if not target_path.exists():
        return {"status": "error", "message": "Model file not found"}
        
    # Update config
    try:
        with open(config_file, "w") as f:
            f.write(filename)
    except Exception as e:
        return {"status": "error", "message": f"Failed to save config: {e}"}
        
    # Update global variable
    MODEL_PATH = str(target_path)
    print(f"[model] Switched active model to: {MODEL_PATH}")
    
    # Restart cameras to pick up new model
    # 1. Stop all running threads
    for cam_id, info in list(camera_threads.items()):
        print(f"[model] Stopping camera {cam_id} for model update...")
        info['stop_event'].set()
        info['thread'].join(timeout=5.0)
        del camera_threads[cam_id]
        
    # 2. Restart online cameras from DB
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(models.Camera))
        cameras = result.scalars().all()
        for cam in cameras:
            if cam.status == "online":
                print(f"[model] Restarting camera {cam.id}...")
                start_camera_thread(cam.id, cam.rtsp_url)
                
    return {"status": "success", "active_model": filename, "path": MODEL_PATH}

@app.post("/api/camera/{camera_id}/start-local")
async def api_start_local_camera(camera_id: int):
    """Start camera thread with local camera (0) instead of RTSP URL."""
    async with AsyncSessionLocal() as session:
        cam = await session.get(models.Camera, camera_id)
        if not cam:
            return {"error": "camera not found"}
        # Use "0" for local camera
        start_camera_thread(cam.id, "0")
    return {"status": "started with local camera", "camera_id": camera_id}


@app.post("/api/camera/{camera_id}/stop")
async def api_stop_camera(camera_id: int):
    info = camera_threads.get(camera_id)
    if not info:
        return {"status": "not running"}
    info['stop_event'].set()
    info['thread'].join(timeout=2.0)
    del camera_threads[camera_id]
    return {"status": "stopped", "camera_id": camera_id}

@app.get("/api/camera/{camera_id}/frame-status")
async def get_frame_status(camera_id: int):
    """Check if frames are available for a camera (for debugging)."""
    frame_bytes = get_latest_frame(camera_id)
    has_frame = frame_bytes is not None
    frame_size = len(frame_bytes) if has_frame else 0
    is_running = camera_id in camera_threads
    
    return {
        "camera_id": camera_id,
        "has_frame": has_frame,
        "frame_size": frame_size,
        "thread_running": is_running,
        "thread_info": {
            "thread_alive": camera_threads[camera_id]['thread'].is_alive() if is_running else False
        } if is_running else None
    }

@app.get("/api/debug/camera-status")
async def debug_camera_status():
    """Debug endpoint to check all camera threads."""
    status = {
        "camera_threads": {},
        "frame_storage": {},
        "total_threads": len(camera_threads)
    }
    
    for cam_id, info in camera_threads.items():
        status["camera_threads"][cam_id] = {
            "thread_alive": info['thread'].is_alive(),
            "stop_event_set": info['stop_event'].is_set()
        }
        
        # Check frame storage for this camera
        frame_bytes = get_latest_frame(cam_id)
        status["frame_storage"][cam_id] = {
            "has_frame": frame_bytes is not None,
            "frame_size": len(frame_bytes) if frame_bytes else 0
        }
    
    return status

@app.get("/api/camera/{camera_id}/stream")
async def stream_camera(camera_id: int):
    """
    MJPEG stream endpoint for live camera feed with detections.
    """
    # Create a placeholder black frame
    placeholder_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(placeholder_frame, "No frame available", (150, 240), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    _, buffer = cv2.imencode('.jpg', placeholder_frame)
    placeholder_bytes = buffer.tobytes()
    
    async def generate_frames():
        consecutive_empty = 0
        while True:
            frame_bytes = get_latest_frame(camera_id)
            if frame_bytes:
                consecutive_empty = 0
                # MJPEG format: frame boundary + frame data
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                consecutive_empty += 1
                # Only send placeholder after a few empty frames to avoid spam
                if consecutive_empty > 10:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + placeholder_bytes + b'\r\n')
            await asyncio.sleep(0.033)  # ~30 FPS
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
