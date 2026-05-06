"""
Edge-worker ingestion: PCs on Tailscale (or LAN) POST violations to Render without a user JWT.
Set WORKER_API_KEY in Render dashboard (same value as on your PC worker .env).
"""
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

import globals as g

router = APIRouter()


class WorkerViolationBody(BaseModel):
    camera_id: int = Field(..., ge=1)
    violations: list[str] = Field(..., min_length=1)
    worker_id: int = 0
    snapshot_path: str | None = None


def _verify_worker_key(x_worker_key: str | None, authorization: str | None) -> None:
    secret = (os.getenv("WORKER_API_KEY") or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="WORKER_API_KEY is not set on the server. Add it in Render environment.",
        )
    if x_worker_key and x_worker_key.strip() == secret:
        return
    if authorization and authorization.startswith("Bearer "):
        if authorization[7:].strip() == secret:
            return
    raise HTTPException(status_code=401, detail="Invalid or missing worker key")


@router.post("/api/worker/violations")
async def worker_ingest_violations(
    body: WorkerViolationBody,
    x_worker_key: str | None = Header(None, alias="X-Worker-Key"),
    authorization: str | None = Header(None),
):
    """
    Queue violation(s) for the same DB path as on-prem camera_runner.
    Headers: X-Worker-Key: <WORKER_API_KEY>  OR  Authorization: Bearer <WORKER_API_KEY>
    """
    _verify_worker_key(x_worker_key, authorization)
    if g.violation_queue is None:
        raise HTTPException(status_code=503, detail="Violation queue not ready")

    await g.violation_queue.put(
        {
            "camera_id": body.camera_id,
            "violations": body.violations,
            "worker_id": body.worker_id,
            "snapshot_path": body.snapshot_path,
        }
    )
    return {"status": "queued", "camera_id": body.camera_id, "violations": body.violations}


@router.get("/api/worker/health")
async def worker_health(
    x_worker_key: str | None = Header(None, alias="X-Worker-Key"),
    authorization: str | None = Header(None),
):
    """Light check that the key works (use from your PC worker on startup)."""
    _verify_worker_key(x_worker_key, authorization)
    return {"status": "ok", "worker_auth": True}
