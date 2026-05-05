"""Global mutable state shared across the application.

Imported as `import globals as g` so callers use `g.camera_threads`, etc.
This makes reads/writes explicit and avoids hidden coupling.
"""
import asyncio
from typing import Optional

# camera_id -> {'thread': Thread, 'stop_event': Event, 'source': str}
camera_threads: dict = {}

violation_queue: Optional[asyncio.Queue] = None
consumer_task = None
main_loop = None
ws_manager = None  # WebSocketManager instance, set at startup
