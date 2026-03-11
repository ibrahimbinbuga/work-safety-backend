import threading
from pathlib import Path
from typing import Dict, Any

from ultralytics import YOLO

# Thread-safe, process-wide model cache
_MODEL_CACHE: Dict[str, Any] = {}
_MODEL_LOCK = threading.Lock()


def resolve_model_path(model_path: str) -> Path:
    """
    Resolve a model path to an absolute filesystem path.

    - If `model_path` is already absolute, it is returned as-is.
    - If it is relative (e.g. "models/file.pt"), it is resolved
      relative to the backend directory (where this file lives).
    """
    p = Path(model_path)
    if not p.is_absolute():
        backend_dir = Path(__file__).parent
        p = backend_dir / p
    return p


def get_model(model_path: str):
    """
    Thread-safe model loading and caching.

    `model_path` may be absolute or relative (e.g. "models/x.pt").
    It is always resolved to an absolute path before loading.

    Returns a cached YOLO model instance for the given path, loading it if needed.
    """
    global _MODEL_CACHE
    resolved_path = resolve_model_path(model_path)
    cache_key = str(resolved_path)

    with _MODEL_LOCK:
        if cache_key not in _MODEL_CACHE:
            try:
                print(f"[model_loader.get_model] Loading model from {resolved_path}")
                model = YOLO(str(resolved_path))
                # Avoid fuse-related issues with older models by not calling fuse() implicitly
                try:
                    if hasattr(model.model, "fuse"):
                        print(
                            "[model_loader.get_model] Model has fuse(), "
                            "will avoid auto-fuse in prediction loops"
                        )
                except Exception:
                    # Best-effort logging; model is still usable
                    pass
                _MODEL_CACHE[cache_key] = model
                print(f"[model_loader.get_model] ✅ Model loaded successfully: {resolved_path}")
            except Exception as e:
                print(f"[model_loader.get_model] Error loading model from {resolved_path}: {e}")
                import traceback

                traceback.print_exc()
                print("[model_loader.get_model] Trying fallback model: yolo11n.pt")

                try:
                    _MODEL_CACHE[cache_key] = YOLO("yolo11n.pt")
                    print("[model_loader.get_model] ✅ Fallback model loaded successfully")
                except Exception as e2:
                    print(f"[model_loader.get_model] Fallback model also failed: {e2}")
                    raise
        return _MODEL_CACHE[cache_key]


def preload_model_async(model_path: str) -> bool:
    """
    Non-blocking model preload in a background thread.

    Returns True if model is already cached, False if background loading was started.
    """
    global _MODEL_CACHE

    resolved_path = resolve_model_path(model_path)
    cache_key = str(resolved_path)

    # Quick check without lock for already-cached models
    if cache_key in _MODEL_CACHE:
        print(f"[model_loader.preload_model_async] Model already cached: {resolved_path}")
        return True

    def load_in_background():
        try:
            get_model(model_path)
        except Exception as e:
            print(f"[model_loader.preload_model_async] Background loading failed: {e}")

    bg_thread = threading.Thread(target=load_in_background, daemon=True)
    bg_thread.start()
    print(f"[model_loader.preload_model_async] Background model loading started for: {resolved_path}")
    return False


def get_models_base_dir() -> Path:
    """
    Central base directory for all model files.

    By convention this is `<backend>/models`.
    """
    backend_dir = Path(__file__).parent
    models_dir = backend_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir

