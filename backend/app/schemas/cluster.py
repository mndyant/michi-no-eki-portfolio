# clusters APIのレスポンス用Pydanticスキーマ
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ClusterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
