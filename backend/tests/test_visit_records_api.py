from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from tests.route_test_data import make_station  # noqa: E402


@pytest.fixture()
def records_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)

    def override_get_db():
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with testing_session() as db:
        db.add(make_station(1, "テスト駅", 34.7, 135.5))
        db.commit()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _record_payload(**overrides: object) -> dict:
    payload = {
        "visit_date": "2026-07-12",
        "purchased_items": ["みかんジュース", "梅干し"],
        "food": ["しらす丼"],
        "impression": "海鮮が安くて新鮮。物産コーナーが広い",
        "want_revisit": True,
        "next_memo": "次は朝市の時間に行く",
    }
    payload.update(overrides)
    return payload


def test_create_record_marks_station_visited(records_client: TestClient) -> None:
    """記録を作ると駅が訪問済みになり、訪問日も記録される。"""
    response = records_client.post(
        "/api/stations/1/visit-records", json=_record_payload()
    )
    assert response.status_code == 201
    body = response.json()
    assert body["purchased_items"] == ["みかんジュース", "梅干し"]
    assert body["impression"].startswith("海鮮")

    station = records_client.get("/api/stations/1").json()
    assert station["visited"] is True
    assert station["visited_date"] == "2026-07-12"


def test_list_records_newest_first(records_client: TestClient) -> None:
    records_client.post(
        "/api/stations/1/visit-records", json=_record_payload(visit_date="2026-06-01")
    )
    records_client.post(
        "/api/stations/1/visit-records", json=_record_payload(visit_date="2026-07-12")
    )
    response = records_client.get("/api/stations/1/visit-records")
    assert response.status_code == 200
    dates = [record["visit_date"] for record in response.json()]
    assert dates == ["2026-07-12", "2026-06-01"]


def test_update_record_partial(records_client: TestClient) -> None:
    created = records_client.post(
        "/api/stations/1/visit-records", json=_record_payload()
    ).json()
    response = records_client.put(
        f"/api/visit-records/{created['id']}",
        json={"impression": "更新後の感想", "purchased_items": ["新しい土産"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["impression"] == "更新後の感想"
    assert body["purchased_items"] == ["新しい土産"]
    # 未指定フィールドは維持される
    assert body["food"] == ["しらす丼"]
    assert body["want_revisit"] is True


def test_update_record_ignores_null_for_required_fields(records_client: TestClient) -> None:
    """NOT NULL列（visit_date/purchased_items/food）への明示的nullは無視して200を返す。

    修正前はNULLがそのままsetattrされ、IntegrityErrorで500になっていた。
    """
    created = records_client.post(
        "/api/stations/1/visit-records", json=_record_payload()
    ).json()
    response = records_client.put(
        f"/api/visit-records/{created['id']}",
        json={"visit_date": None, "purchased_items": None, "food": None, "impression": None},
    )
    assert response.status_code == 200
    body = response.json()
    # NOT NULL列は変更されず、null許容列（impression）だけがクリアされる
    assert body["visit_date"] == "2026-07-12"
    assert body["purchased_items"] == ["みかんジュース", "梅干し"]
    assert body["food"] == ["しらす丼"]
    assert body["impression"] is None


def test_delete_record(records_client: TestClient) -> None:
    created = records_client.post(
        "/api/stations/1/visit-records", json=_record_payload()
    ).json()
    response = records_client.delete(f"/api/visit-records/{created['id']}")
    assert response.status_code == 204
    assert records_client.get("/api/stations/1/visit-records").json() == []


def test_record_for_unknown_station_is_404(records_client: TestClient) -> None:
    response = records_client.post(
        "/api/stations/999/visit-records", json=_record_payload()
    )
    assert response.status_code == 404


def test_update_unknown_record_is_404(records_client: TestClient) -> None:
    response = records_client.put("/api/visit-records/999", json={"impression": "x"})
    assert response.status_code == 404


# --- 写真アップロード（Issue #48） ---

# 1x1ピクセルの最小PNG（バイナリを直接持つとテストが読みにくいためbase64で保持）
import base64  # noqa: E402

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQAB"
    "h6FO1AAAAABJRU5ErkJggg=="
)


@pytest.fixture()
def photo_dir(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """テスト中の写真保存先を一時ディレクトリに差し替える。"""
    import app.api.photos as photos_module

    monkeypatch.setattr(photos_module, "PHOTOS_DIR", tmp_path)
    return tmp_path


def _create_record(client: TestClient) -> int:
    return client.post("/api/stations/1/visit-records", json=_record_payload()).json()["id"]


def test_upload_photo_with_tags(records_client: TestClient, photo_dir) -> None:
    record_id = _create_record(records_client)
    response = records_client.post(
        f"/api/visit-records/{record_id}/photos",
        files={"file": ("photo.png", TINY_PNG, "image/png")},
        data={"tags": "名産品、みかんジュース"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["url"].startswith("/photos/")
    assert body["tags"] == ["名産品", "みかんジュース"]
    # 実ファイルが保存されている
    assert (photo_dir / body["url"].removeprefix("/photos/")).exists()
    # 記録の取得に写真が含まれる
    records = records_client.get("/api/stations/1/visit-records").json()
    assert records[0]["photos"][0]["id"] == body["id"]


def test_update_photo_tags(records_client: TestClient, photo_dir) -> None:
    record_id = _create_record(records_client)
    photo = records_client.post(
        f"/api/visit-records/{record_id}/photos",
        files={"file": ("photo.png", TINY_PNG, "image/png")},
    ).json()
    response = records_client.put(
        f"/api/photos/{photo['id']}", json={"tags": ["外観"]}
    )
    assert response.status_code == 200
    assert response.json()["tags"] == ["外観"]


def test_delete_photo_removes_file(records_client: TestClient, photo_dir) -> None:
    record_id = _create_record(records_client)
    photo = records_client.post(
        f"/api/visit-records/{record_id}/photos",
        files={"file": ("photo.png", TINY_PNG, "image/png")},
    ).json()
    file_path = photo_dir / photo["url"].removeprefix("/photos/")
    assert file_path.exists()
    response = records_client.delete(f"/api/photos/{photo['id']}")
    assert response.status_code == 204
    assert not file_path.exists()


def test_upload_photo_rejects_non_image(records_client: TestClient, photo_dir) -> None:
    record_id = _create_record(records_client)
    response = records_client.post(
        f"/api/visit-records/{record_id}/photos",
        files={"file": ("script.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 422


def test_upload_photo_unknown_record_is_404(records_client: TestClient, photo_dir) -> None:
    response = records_client.post(
        "/api/visit-records/999/photos",
        files={"file": ("photo.png", TINY_PNG, "image/png")},
    )
    assert response.status_code == 404
