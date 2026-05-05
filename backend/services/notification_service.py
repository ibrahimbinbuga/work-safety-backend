"""Real-time violation notification service: WebSocket broadcast + FCM push."""
import asyncio
import json
import os
from collections import defaultdict

from fastapi import WebSocket

import firebase_admin
from firebase_admin import credentials, messaging

_firebase_initialized = False


class WebSocketManager:
    """In-memory registry of active WebSocket connections, keyed by company_id."""

    def __init__(self):
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    def disconnect(self, websocket: WebSocket, company_id: int):
        self._connections[company_id].discard(websocket)
        if not self._connections[company_id]:
            del self._connections[company_id]

    async def broadcast_to_company(self, company_id: int, message: dict):
        sockets = list(self._connections.get(company_id, set()))
        print(f"[WS] Broadcasting to company {company_id} — {len(sockets)} client(s) connected")
        if not sockets:
            return
        payload = json.dumps(message)
        dead = []
        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception as e:
                print(f"[WS] Send error: {e}")
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, company_id)


def _ensure_firebase():
    global _firebase_initialized
    if not _firebase_initialized:
        service_account_path = os.getenv(
            "FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json"
        )
        print(f"[FCM] Loading service account: {service_account_path}")
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        print("[FCM] Firebase initialized OK")


async def _send_fcm(tokens: list[str], title: str, body: str, data: dict) -> list[str]:
    """Send multicast FCM push. Returns list of invalid token strings to delete."""
    if not tokens:
        print("[FCM] No tokens to send to")
        return []
    _ensure_firebase()
    print(f"[FCM] Sending to {len(tokens)} token(s) — title: {title}")
    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in data.items()},
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default", badge=1))
        ),
    )
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, messaging.send_each_for_multicast, message)
    print(f"[FCM] Success: {response.success_count}, Failure: {response.failure_count}")
    invalid = []
    for idx, result in enumerate(response.responses):
        if not result.success:
            code = getattr(result.exception, "code", "")
            print(f"[FCM] Token[{idx}] failed — code: {code}, error: {result.exception}")
            if code in ("registration-token-not-registered", "invalid-argument"):
                invalid.append(tokens[idx])
    return invalid


async def send_violation_notifications(
    company_id: int,
    violation_type: str,
    camera_id: int,
    camera_location: str,
    snapshot_path: str | None,
    timestamp: str,
):
    """
    Called after a violation is persisted to DB.
    Always broadcasts via WebSocket; sends FCM only if push_enabled is True.
    """
    import globals as g
    from database import AsyncSessionLocal
    import models
    from sqlalchemy import select

    print(f"[NOTIF] Violation: type={violation_type}, camera={camera_id}, company={company_id}")

    ws_payload = {
        "event": "violation",
        "company_id": company_id,
        "violation_type": violation_type,
        "camera_id": camera_id,
        "camera_location": camera_location,
        "snapshot_path": snapshot_path,
        "timestamp": timestamp,
    }

    if g.ws_manager:
        await g.ws_manager.broadcast_to_company(company_id, ws_payload)

    async with AsyncSessionLocal() as db:
        settings = (await db.execute(
            select(models.CompanyNotificationSettings).where(
                models.CompanyNotificationSettings.company_id == company_id
            )
        )).scalar_one_or_none()

        if not settings:
            print(f"[NOTIF] No notification settings for company {company_id} — skipping FCM")
            return
        if not settings.push_enabled:
            print(f"[NOTIF] push_enabled=False for company {company_id} — skipping FCM")
            return

        rows = (await db.execute(
            select(models.DeviceToken.token, models.DeviceToken.id).where(
                models.DeviceToken.company_id == company_id
            )
        )).all()

        print(f"[NOTIF] Found {len(rows)} device token(s) for company {company_id}")
        if not rows:
            return

        token_strings = [r.token for r in rows]
        token_id_map = {r.token: r.id for r in rows}

        labels = {
            "head": "No Helmet Detected",
            "vest": "No Vest Detected",
            "fall": "Worker Fall Detected",
            "fallen": "Worker Fall Detected",
        }
        body = labels.get(violation_type, f"Violation: {violation_type}")
        body += f" — Camera: {camera_location or camera_id}"

        invalid = await _send_fcm(
            token_strings,
            title="Safety Violation Alert",
            body=body,
            data={
                "company_id": company_id,
                "violation_type": violation_type,
                "camera_id": camera_id,
                "timestamp": timestamp,
            },
        )

        if invalid:
            invalid_ids = [token_id_map[t] for t in invalid if t in token_id_map]
            if invalid_ids:
                from sqlalchemy import delete as sql_delete
                await db.execute(
                    sql_delete(models.DeviceToken).where(
                        models.DeviceToken.id.in_(invalid_ids)
                    )
                )
                await db.commit()
                print(f"[FCM] Removed {len(invalid_ids)} stale token(s) for company {company_id}")
