"""Shared mutable runtime state."""

import asyncio
from typing import Optional

camera_threads: dict = {}
violation_queue: Optional[asyncio.Queue] = None
consumer_task = None
main_loop = None
