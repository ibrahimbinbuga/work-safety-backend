"""Violation queue consumer and DB persistence logic."""
import asyncio
import traceback

from database import AsyncSessionLocal
import models


async def violation_consumer_task(queue: asyncio.Queue):
    """Consume violation payloads from the queue and persist them to the DB."""
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
    """Persist a violation payload as Detection + Violation rows."""
    async with AsyncSessionLocal() as session:
        try:
            camera_id = payload.get('camera_id')
            if camera_id is None:
                print("[consumer] payload has no camera_id, skipping violation save")
                return

            cam = await session.get(models.Camera, camera_id)
            if cam is None or cam.company_id is None:
                print(f"[consumer] Camera {camera_id} has no company_id, skipping violation save")
                return

            company_id = cam.company_id
            allowed_types = ('head', 'vest', 'person', 'sitting', 'fallen', 'standing', 'fall')

            for v in payload.get('violations', []):
                if v not in allowed_types:
                    print(f"[consumer] Invalid violation type: {v}, skipping...")
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
                    print(f"[consumer] Warning: worker_id is None for violation {v}, using 0 as default")
                    worker_id = 0

                session.add(models.Violations(
                    company_id=company_id,
                    ihlal_cesidi=v,
                    ihlal_yapilan_bolge=str(camera_id),
                    violation_id=int(worker_id),
                ))

            await session.commit()
            print(
                f"[consumer] Saved violation(s) for camera {camera_id} - "
                f"{payload.get('violations')}, worker_id={payload.get('worker_id')}"
            )

            import datetime as _dt
            from services.notification_service import send_violation_notifications
            _ts = _dt.datetime.utcnow().isoformat() + "Z"
            _loc = str(cam.location or camera_id)
            for _v in payload.get('violations', []):
                if _v not in allowed_types:
                    continue
                try:
                    await send_violation_notifications(
                        company_id=company_id,
                        violation_type=_v,
                        camera_id=camera_id,
                        camera_location=_loc,
                        snapshot_path=payload.get('snapshot_path'),
                        timestamp=_ts,
                    )
                except Exception as _ne:
                    print(f"[consumer] Notification error for {_v}: {_ne}")
        except Exception as e:
            await session.rollback()
            print(f"[consumer] Error saving violation: {e}")
            traceback.print_exc()
            raise
