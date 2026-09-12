from __future__ import annotations

from pydantic import BaseModel, Field

# 訪問記録の写真スキーマ（Issue #48）。
# 実ファイルは /photos/{file_name} で静的配信し、APIはメタ情報（URL・タグ）を扱う


class VisitPhotoRead(BaseModel):
    id: int
    visit_record_id: int
    url: str  # 例: /photos/12_a1b2c3.jpg（フロントはAPIベースURLと結合して表示）
    tags: list[str]


class VisitPhotoTagsUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list)
