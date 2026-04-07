"""Model upload, activation, company-model management, and detection endpoints."""
import base64
import traceback
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenData
from database import AsyncSessionLocal, get_db
from dependencies import get_admin_user, get_current_user, verify_company_access
import models
from services.camera_service import (
    camera_to_dict,
    restart_camera_with_current_models,
    restart_company_cameras,
)
from services.model_service import (
    general_model_to_dict,
    get_camera_active_models,
    modelmeta_to_dict,
    set_active_model_path,
    get_active_model_path,
    sync_company_model_activation_summary,
    PRIORITY_INTERVALS,
    get_violation_check_interval_for_camera,
)
from services.camera_service import restart_camera_with_current_models as _restart_camera

router = APIRouter()

# ---------------------------------------------------------------------------
# Global model endpoints
# ---------------------------------------------------------------------------

@router.post("/api/model/upload")
async def upload_model(
    file: UploadFile = File(...),
    version: str = Form(...),
    description: Optional[str] = Form(None),
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    allowed_ext = ('.pt', '.weights', '.onnx')
    if not any(file.filename.endswith(ext) for ext in allowed_ext):
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya uzantisi.")

    try:
        # routes/models.py is backend/routes/models.py → parent.parent.parent = project root
        project_root = Path(__file__).parent.parent.parent
        models_dir = project_root / "model" / "weights"
        models_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{version}_{uuid.uuid4().hex}_{file.filename}"
        file_path = models_dir / filename
        relative_path = file_path.relative_to(project_root).as_posix()

        MAX_SIZE = 200 * 1024 * 1024
        content = await file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="Model dosyasi cok buyuk (max 200MB).")

        with open(file_path, "wb") as f:
            f.write(content)
        print(f"[model] Model dosyasi yuklendi: {file_path} (stored as: {relative_path})")

        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(models.ModelMeta).where(models.ModelMeta.path == relative_path)
            )
            if existing.scalars().first():
                raise HTTPException(status_code=409, detail="Bu path ile model zaten var.")
            session.add(models.ModelMeta(
                path=relative_path, version=version, description=description, is_active=False
            ))
            await session.commit()

        return {"status": "success", "path": relative_path, "version": version, "description": description}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model yukleme hatasi: {str(e)}")


@router.post("/api/model/activate")
async def activate_model(
    path: str = Form(...),
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if not path:
        set_active_model_path("")
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(models.Camera))
            for cam in result.scalars().all():
                await restart_camera_with_current_models(session, cam)
        return {"status": "active", "model_path": None}

    if not Path(path).exists():
        raise HTTPException(status_code=404, detail="Model dosyasi bulunamadi.")

    set_active_model_path(path)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(models.Camera))
        for cam in result.scalars().all():
            await restart_camera_with_current_models(session, cam)

    async with AsyncSessionLocal() as session:
        await session.execute(update(models.ModelMeta).values(is_active=False))
        await session.execute(
            update(models.ModelMeta).where(models.ModelMeta.path == path).values(is_active=True)
        )
        await session.commit()

    return {"status": "active", "model_path": path}


@router.get("/api/model/active")
async def get_active_model(current_user: TokenData = Depends(get_current_user)):
    return {"active_model_path": get_active_model_path()}


@router.get("/api/models")
async def get_models_list(current_user: TokenData = Depends(get_current_user)):
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(models.ModelMeta).order_by(models.ModelMeta.uploaded_at.desc())
            )
            return [modelmeta_to_dict(m) for m in result.scalars().all()]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model listesi alinamadi: {str(e)}")


@router.get("/api/general-models")
async def get_general_models(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.ModelMeta).order_by(models.ModelMeta.uploaded_at.desc()))
    return [general_model_to_dict(m) for m in result.scalars().all()]


# ---------------------------------------------------------------------------
# Company-scoped model endpoints
# ---------------------------------------------------------------------------

@router.get("/api/company/{company_code}/general-models")
async def get_company_general_models(
    company_code: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_company_access(current_user, company_code)

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Sirket bulunamadi")

    result = await db.execute(
        select(models.ModelMeta)
        .join(models.CompanyModel, models.CompanyModel.model_id == models.ModelMeta.id)
        .where(models.CompanyModel.company_id == company.id)
        .order_by(models.ModelMeta.uploaded_at.desc())
    )
    return [general_model_to_dict(m) for m in result.scalars().all()]


@router.put("/api/company/{company_code}/general-models")
async def set_company_general_models(
    company_code: str,
    payload: dict,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk-update the model list assigned to a company. Body: { model_ids: number[] }"""
    model_ids = payload.get("model_ids", []) if isinstance(payload, dict) else []
    if not isinstance(model_ids, list):
        raise HTTPException(status_code=400, detail="model_ids list olmalidir")
    normalized_model_ids = list(dict.fromkeys(int(mid) for mid in model_ids))

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Sirket bulunamadi")

    valid_model_ids: set = set()
    if normalized_model_ids:
        valid_result = await db.execute(
            select(models.ModelMeta.id).where(models.ModelMeta.id.in_(normalized_model_ids))
        )
        valid_model_ids = set(valid_result.scalars().all())

    existing_result = await db.execute(
        select(models.CompanyModel).where(models.CompanyModel.company_id == company.id)
    )
    existing_model_ids = {cm.model_id for cm in existing_result.scalars().all()}

    removed_ids = existing_model_ids - valid_model_ids
    added_ids = valid_model_ids - existing_model_ids

    if removed_ids:
        await db.execute(
            delete(models.CompanyModelCamera).where(
                (models.CompanyModelCamera.company_id == company.id)
                & (models.CompanyModelCamera.model_id.in_(removed_ids))
            )
        )
        await db.execute(
            delete(models.CompanyModel).where(
                (models.CompanyModel.company_id == company.id)
                & (models.CompanyModel.model_id.in_(removed_ids))
            )
        )

    for mid in added_ids:
        db.add(models.CompanyModel(company_id=company.id, model_id=mid, is_active=False))

    await sync_company_model_activation_summary(db, company.id)
    await db.commit()
    await restart_company_cameras(db, company.id)
    return {"status": "success", "assigned_count": len(valid_model_ids)}


@router.get("/api/company/{company_code}/model-cameras")
async def get_company_model_cameras(
    company_code: str,
    model_id: Optional[int] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_company_access(current_user, company_code)

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Sirket bulunamadi")

    cameras_result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company.id)
    )

    # model_id verilmişse her kamera için priority ve assignment_id bilgisini getir
    priority_by_camera = {}
    if model_id is not None:
        assignments_result = await db.execute(
            select(
                models.CompanyModelCamera.camera_id,
                models.CompanyModelCamera.priority,
                models.CompanyModelCamera.id,
            )
            .where(
                (models.CompanyModelCamera.company_id == company.id)
                & (models.CompanyModelCamera.model_id == model_id)
            )
        )
        for row in assignments_result:
            priority_by_camera[row.camera_id] = {
                "priority": str(row.priority) if row.priority else "medium",
                "assignment_id": row.id,
            }

    response = []
    for cam in cameras_result.scalars().all():
        active_models = await get_camera_active_models(db, company.id, cam.id)
        active_ids = {m["id"] for m in active_models}
        is_active = (model_id in active_ids) if model_id is not None else bool(active_ids)
        cam_dict = camera_to_dict(cam, active_models=active_models, model_is_active=is_active)
        if model_id is not None and cam.id in priority_by_camera:
            cam_dict["priority"] = priority_by_camera[cam.id]["priority"]
            cam_dict["assignment_id"] = priority_by_camera[cam.id]["assignment_id"]
        elif model_id is not None:
            cam_dict["priority"] = "medium"
            cam_dict["assignment_id"] = None
        response.append(cam_dict)
    return response


@router.put("/api/company/{company_code}/model-cameras")
async def set_company_model_cameras(
    company_code: str,
    payload: dict,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update model-camera assignment. Body: { model_id: number, camera_ids: number[] }"""
    await verify_company_access(current_user, company_code)

    model_id = payload.get("model_id") if isinstance(payload, dict) else None
    camera_ids = payload.get("camera_ids", []) if isinstance(payload, dict) else []
    camera_priorities: dict = payload.get("camera_priorities", {}) if isinstance(payload, dict) else {}

    if model_id is None:
        raise HTTPException(status_code=400, detail="model_id zorunludur")
    if not isinstance(camera_ids, list):
        raise HTTPException(status_code=400, detail="camera_ids list olmalidir")

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Sirket bulunamadi")

    company_model_result = await db.execute(
        select(models.CompanyModel).where(
            (models.CompanyModel.company_id == company.id)
            & (models.CompanyModel.model_id == int(model_id))
        )
    )
    if not company_model_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Model bu sirkete atanmamis")

    valid_cam_ids_result = await db.execute(
        select(models.Camera.id).where(models.Camera.company_id == company.id)
    )
    valid_cam_ids = set(valid_cam_ids_result.scalars().all())
    invalid = [cid for cid in camera_ids if int(cid) not in valid_cam_ids]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Gecersiz camera_ids: {invalid}")

    normalized_cam_ids = {int(cid) for cid in camera_ids}

    existing_result = await db.execute(
        select(models.CompanyModelCamera).where(
            (models.CompanyModelCamera.company_id == company.id)
            & (models.CompanyModelCamera.model_id == int(model_id))
        )
    )
    assignments_by_camera = {a.camera_id: a for a in existing_result.scalars().all()}

    for cam_id in valid_cam_ids:
        should_be_active = cam_id in normalized_cam_ids
        assignment = assignments_by_camera.get(cam_id)
        new_priority = camera_priorities.get(str(cam_id))
        if assignment:
            assignment.is_active = should_be_active
            if new_priority and new_priority in PRIORITY_INTERVALS:
                assignment.priority = new_priority
        elif should_be_active:
            db.add(models.CompanyModelCamera(
                company_id=company.id,
                camera_id=cam_id,
                model_id=int(model_id),
                is_active=True,
                priority=new_priority if new_priority and new_priority in PRIORITY_INTERVALS else "medium",
            ))

    await sync_company_model_activation_summary(db, company.id)
    await db.commit()
    await restart_company_cameras(db, company.id)

    return {
        "status": "success",
        "model_id": int(model_id),
        "selected_camera_count": len(normalized_cam_ids),
        "note": "Camera-level model mapping applied. Multiple models can run on the same camera.",
    }


@router.get("/api/company/{company_code}/models")
async def get_company_models(
    company_code: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_company_access(current_user, company_code)

    try:
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="Sirket bulunamadi")

        result = await db.execute(
            select(models.CompanyModel)
            .where(models.CompanyModel.company_id == company.id)
            .join(models.ModelMeta)
            .order_by(models.ModelMeta.version.desc())
        )
        return [
            {
                "id": cm.id,
                "model_id": cm.model_id,
                "company_id": cm.company_id,
                "is_active": cm.is_active,
                "enabled_at": cm.enabled_at.isoformat() if cm.enabled_at else "",
                "model": {
                    "id": cm.model.id,
                    "path": cm.model.path,
                    "version": cm.model.version,
                    "description": cm.model.description,
                    "uploaded_at": cm.model.uploaded_at.isoformat() if cm.model.uploaded_at else "",
                },
            }
            for cm in result.scalars().all()
        ]
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model listesi alinamadi: {str(e)}")


@router.post("/api/company/{company_code}/models/{model_id}/assign")
async def assign_model_to_company(
    company_code: str,
    model_id: int,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="Sirket bulunamadi")

        model_result = await db.execute(
            select(models.ModelMeta).where(models.ModelMeta.id == model_id)
        )
        model = model_result.scalars().first()
        if not model:
            raise HTTPException(status_code=404, detail="Model bulunamadi")

        existing = await db.execute(
            select(models.CompanyModel).where(
                (models.CompanyModel.company_id == company.id)
                & (models.CompanyModel.model_id == model_id)
            )
        )
        if existing.scalars().first():
            raise HTTPException(status_code=409, detail="Model zaten bu sirkete atanmis")

        db.add(models.CompanyModel(company_id=company.id, model_id=model_id, is_active=False))
        await db.commit()
        return {"status": "success", "message": f"Model {model.version} sirkete {company.name} atandi"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model atama hatasi: {str(e)}")


@router.post("/api/company/{company_code}/models/{company_model_id}/activate")
async def activate_model_for_company(
    company_code: str,
    company_model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_company_access(current_user, company_code)

    try:
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="Sirket bulunamadi")

        cm_result = await db.execute(
            select(models.CompanyModel).where(
                (models.CompanyModel.id == company_model_id)
                & (models.CompanyModel.company_id == company.id)
            )
        )
        company_model = cm_result.scalars().first()
        if not company_model:
            raise HTTPException(status_code=404, detail="Model atamasi bulunamadi")

        cameras_result = await db.execute(
            select(models.Camera).where(models.Camera.company_id == company.id)
        )
        cameras = cameras_result.scalars().all()
        if not cameras:
            raise HTTPException(status_code=400, detail="Sirkete ait kamera bulunamadi")

        assignments_result = await db.execute(
            select(models.CompanyModelCamera).where(
                (models.CompanyModelCamera.company_id == company.id)
                & (models.CompanyModelCamera.model_id == company_model.model_id)
            )
        )
        assignments_by_camera = {a.camera_id: a for a in assignments_result.scalars().all()}

        for camera in cameras:
            assignment = assignments_by_camera.get(camera.id)
            if assignment:
                assignment.is_active = True
            else:
                db.add(models.CompanyModelCamera(
                    company_id=company.id,
                    camera_id=camera.id,
                    model_id=company_model.model_id,
                    is_active=True,
                ))

        await sync_company_model_activation_summary(db, company.id)
        await db.commit()
        await restart_company_cameras(db, company.id)
        return {
            "status": "success",
            "message": f"Model {company_model.model.version} sirkete ait tum kameralarda aktiflestirildi",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model aktivasyon hatasi: {str(e)}")


@router.post("/api/company/{company_code}/models/{company_model_id}/deactivate")
async def deactivate_model_for_company(
    company_code: str,
    company_model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_company_access(current_user, company_code)

    try:
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="Sirket bulunamadi")

        cm_result = await db.execute(
            select(models.CompanyModel).where(
                (models.CompanyModel.id == company_model_id)
                & (models.CompanyModel.company_id == company.id)
            )
        )
        company_model = cm_result.scalars().first()
        if not company_model:
            raise HTTPException(status_code=404, detail="Model atamasi bulunamadi")

        await db.execute(
            update(models.CompanyModelCamera)
            .where(
                (models.CompanyModelCamera.company_id == company.id)
                & (models.CompanyModelCamera.model_id == company_model.model_id)
            )
            .values(is_active=False)
        )
        await sync_company_model_activation_summary(db, company.id)
        await db.commit()
        await restart_company_cameras(db, company.id)
        return {
            "status": "success",
            "message": f"Model {company_model.model.version} tum company kameralarinda deaktiflestirildi",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model deaktivasyonu hatasi: {str(e)}")


# ---------------------------------------------------------------------------
# Priority endpoint
# ---------------------------------------------------------------------------

@router.patch("/api/company/{company_code}/model-cameras/{assignment_id}/priority")
async def update_camera_model_priority(
    company_code: str,
    assignment_id: int,
    payload: dict,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kamera-model atamasının önceliğini günceller. Admin ve user kullanabilir."""
    await verify_company_access(current_user, company_code)

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Sirket bulunamadi")

    priority = payload.get("priority")
    if priority not in PRIORITY_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Gecersiz oncelik. Gecerli degerler: {list(PRIORITY_INTERVALS.keys())}",
        )

    assignment_result = await db.execute(
        select(models.CompanyModelCamera).where(
            (models.CompanyModelCamera.id == assignment_id)
            & (models.CompanyModelCamera.company_id == company.id)
        )
    )
    assignment = assignment_result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Kamera-model ataması bulunamadi")

    assignment.priority = priority
    await db.commit()

    # Kamera çalışıyorsa yeni interval ile yeniden başlat
    import globals as g
    camera = await db.get(models.Camera, assignment.camera_id)
    if camera and assignment.camera_id in g.camera_threads:
        await _restart_camera(db, camera)

    return {
        "status": "success",
        "assignment_id": assignment_id,
        "priority": priority,
        "interval_seconds": PRIORITY_INTERVALS[priority],
    }


# ---------------------------------------------------------------------------
# Detection endpoint
# ---------------------------------------------------------------------------

@router.post("/api/detect")
async def detect(
    file: UploadFile = File(...),
    model_path: str = Form(...),
    current_user: TokenData = Depends(get_current_user),
):
    """Run uploaded image through a YOLO model and return annotated result."""
    try:
        if not model_path:
            return {"status": "error", "message": "Model yolu gecersiz. Lutfen bir model aktif edin."}

        from ultralytics import YOLO

        if not Path(model_path).exists():
            return {"status": "error", "message": f"Model dosyasi bulunamadi: {model_path}"}

        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"status": "error", "message": "Resim dosyasi okunamadi. Lutfen gecerli bir resim secin."}

        model = YOLO(model_path)
        results = model(img)

        detections = [
            {"class": model.names[int(box.cls)], "confidence": float(box.conf), "bbox": box.xyxy[0].tolist()}
            for r in results
            for box in r.boxes
        ]

        annotated_img = results[0].plot()
        _, buffer = cv2.imencode('.jpg', annotated_img)
        image_base64 = base64.b64encode(buffer).decode()

        return {
            "status": "success",
            "detections": len(detections),
            "objects": detections,
            "image_base64": image_base64,
            "processing_time": results[0].speed.get('inference', 0),
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"Detection hatasi: {str(e)}"}
