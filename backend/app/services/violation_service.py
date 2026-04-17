"""Violation queue consumer and DB persistence logic."""
import asyncio
import traceback

from app.db.session import AsyncSessionLocal
from app.db import models


async def violation_consumer_task(queue: asyncio.Queue):
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
    async with AsyncSessionLocal() as session:
        try:
            camera_id = payload.get('camera_id')
            if camera_id is None:
                return

            cam = await session.get(models.Camera, camera_id)
            if cam is None or cam.company_id is None:
                return

            company_id = cam.company_id
            allowed_types = ('head', 'vest', 'person', 'sitting', 'fallen', 'standing', 'fall')

            for v in payload.get('violations', []):
                if v not in allowed_types:
                    continue

                session.add(models.Detection(
                    camera_id=camera_id,
                    company_id=company_id,
                    detection_type=v,
                    confidence=None,
                    is_violation=True,
                    snapshot_path=payload.get('snapshot_path'),
                ))

                worker_id = payload.get('worker_id')
                if worker_id is None:
                    worker_id = 0

                session.add(models.Violations(
                    company_id=company_id,
                    ihlal_cesidi=v,
                    ihlal_yapilan_bolge=str(camera_id),
                    violation_id=int(worker_id),
                ))

            await session.commit()
        except Exception:
            await session.rollback()
            traceback.print_exc()
            raise
