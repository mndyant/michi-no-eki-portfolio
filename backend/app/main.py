# FastAPIアプリのエントリポイント
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.clusters import router as clusters_router
from app.api.photos import PHOTOS_DIR, router as photos_router
from app.api.routes import router as routes_router
from app.api.stations import router as stations_router
from app.api.visit_records import router as visit_records_router

app = FastAPI(
    title="近畿道の駅スタンプラリー巡回計画AI API",
    description="道の駅の巡回計画・意思決定支援アプリのバックエンドAPI",
    version="0.1.0",
)

# フロントエンド（Next.js）からのアクセスを許可する。
# ローカル開発ではポート競合により3000以外（3001, 3002...）で起動することが多いため、
# localhost/127.0.0.1の任意ポートを許可する。本番運用時はオリジンを絞り込む想定。
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """サーバーが正常に起動しているか確認するためのヘルスチェック用エンドポイント"""
    return {"status": "ok"}


# 道の駅CRUD API（Issue #5）
app.include_router(stations_router)
app.include_router(clusters_router)
app.include_router(routes_router)
app.include_router(visit_records_router)
app.include_router(photos_router)

# 訪問記録の写真を静的配信する（保存先: リポジトリ直下 data/photos/、git管理外）
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")
