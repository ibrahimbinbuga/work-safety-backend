"""Aggregated API router."""

from fastapi import APIRouter

from app.api.v1 import auth, cameras, detections, reports, users
from app.api.v1.models import router as models_router

router = APIRouter()
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(cameras.router)
router.include_router(detections.router)
router.include_router(models_router)
router.include_router(reports.router)
