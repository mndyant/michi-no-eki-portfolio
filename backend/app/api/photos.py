from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.visit_photo import VisitPhoto
from app.models.visit_record import VisitRecord
from app.schemas.visit_photo import VisitPhotoRead, VisitPhotoTagsUpdate

# 写真の保存先はリポジトリ直下の data/photos/（git管理外、DESIGN.md 12章のdata配置方針に合わせる）
REPO_ROOT = Path(__file__).resolve().parents[3]
PHOTOS_DIR = REPO_ROOT / "data" / "photos"

# 受け付ける画像拡張子と上限サイズ（スマホ写真1枚を想定して8MB）
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PHOTO_BYTES = 8 * 1024 * 1024

router = APIRouter(prefix="/api", tags=["photos"])


def _to_read(photo: VisitPhoto) -> VisitPhotoRead:
    return VisitPhotoRead(
        id=photo.id,
        visit_record_id=photo.visit_record_id,
        url=f"/photos/{photo.file_name}",
        tags=json.loads(photo.tags),
    )


def _parse_tags(tags_text: str) -> list[str]:
    """「名産品、みかんジュース」のようなカンマ区切りをタグ配列にする。"""
    normalized = tags_text.replace("、", ",")
    return [tag.strip() for tag in normalized.split(",") if tag.strip()]


@router.post(
    "/visit-records/{record_id}/photos",
    response_model=VisitPhotoRead,
    status_code=201,
)
async def upload_photo(
    record_id: int,
    file: UploadFile = File(...),
    tags: str = Form(""),
    db: Session = Depends(get_db),
) -> VisitPhotoRead:
    """訪問記録に写真を1枚追加する。tagsは「、」またはカンマ区切りの文字列。"""
    record = db.get(VisitRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"訪問記録（id={record_id}）が見つかりません")

    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"対応していない画像形式です（対応: {'/'.join(sorted(ALLOWED_EXTENSIONS))}）",
        )
    content = await file.read()
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=422, detail="写真は8MB以下にしてください")
    if not content:
        raise HTTPException(status_code=422, detail="空のファイルはアップロードできません")

    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{record_id}_{uuid.uuid4().hex}{extension}"
    (PHOTOS_DIR / file_name).write_bytes(content)

    photo = VisitPhoto(
        visit_record_id=record_id,
        file_name=file_name,
        tags=json.dumps(_parse_tags(tags), ensure_ascii=False),
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return _to_read(photo)


@router.put("/photos/{photo_id}", response_model=VisitPhotoRead)
def update_photo_tags(
    photo_id: int, payload: VisitPhotoTagsUpdate, db: Session = Depends(get_db)
) -> VisitPhotoRead:
    """写真のタグを付け替える。"""
    photo = db.get(VisitPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail=f"写真（id={photo_id}）が見つかりません")
    photo.tags = json.dumps(payload.tags, ensure_ascii=False)
    db.commit()
    db.refresh(photo)
    return _to_read(photo)


@router.delete("/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: int, db: Session = Depends(get_db)) -> None:
    """写真を削除する（DB行と実ファイルの両方）。"""
    photo = db.get(VisitPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail=f"写真（id={photo_id}）が見つかりません")
    file_path = PHOTOS_DIR / photo.file_name
    db.delete(photo)
    db.commit()
    # ファイル削除はDB削除の後に行い、失敗しても（手動削除済み等）APIは成功とする
    file_path.unlink(missing_ok=True)
