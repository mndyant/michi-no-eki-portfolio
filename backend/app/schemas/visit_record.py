from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.visit_photo import VisitPhotoRead

# 訪問記録のスキーマ（DESIGN.md 5章 visit_records / 13-3章）。
# DBでは purchased_items / food をJSON文字列で持つが、APIでは文字列配列で受け渡す


class VisitRecordBase(BaseModel):
    visit_date: date
    purchased_items: list[str] = Field(default_factory=list)  # 買ってよかったもの等
    food: list[str] = Field(default_factory=list)  # 食べたもの
    impression: str | None = None  # 感想・特色メモ
    photo_url: str | None = None
    want_revisit: bool | None = None  # また行きたいか（未回答はNone）
    next_memo: str | None = None  # 次回訪問時のメモ


class VisitRecordCreate(VisitRecordBase):
    pass


class VisitRecordUpdate(BaseModel):
    """部分更新用。渡されたフィールドだけ上書きする。"""

    visit_date: date | None = None
    purchased_items: list[str] | None = None
    food: list[str] | None = None
    impression: str | None = None
    photo_url: str | None = None
    want_revisit: bool | None = None
    next_memo: str | None = None


class VisitRecordRead(VisitRecordBase):
    id: int
    station_id: int
    photos: list[VisitPhotoRead] = Field(default_factory=list)
