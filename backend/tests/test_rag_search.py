# FTS5全文検索（app/services/rag/search.py）の結合テスト
# インメモリSQLiteにchunks/chunks_ftsを作り、実際にMATCH検索する
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, create_fts_tables  # noqa: E402
from app.models.chunk import Chunk  # noqa: E402
from app.services.rag.search import search_chunks  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    create_fts_tables(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    chunks = [
        Chunk(station_id="P35_001", chunk_type="wikipedia", content="丹後地方の名産品を販売する観光施設"),
        Chunk(station_id="P35_002", chunk_type="wikipedia", content="国道8号沿いにある道の駅である"),
        Chunk(station_id="P35_001", chunk_type="basic", content="住所: 舞鶴市"),
    ]
    session.add_all(chunks)
    session.commit()
    for chunk in chunks:
        session.execute(
            text("INSERT INTO chunks_fts(rowid, content) VALUES (:id, :content)"),
            {"id": chunk.id, "content": chunk.content},
        )
    session.commit()

    yield session
    session.close()


def test_キーワードにマッチするチャンクが返る(db_session):
    result = search_chunks(db_session, "名産品")
    assert len(result) == 1
    assert result[0]["station_id"] == "P35_001"


def test_マッチしないキーワードは空リスト(db_session):
    assert search_chunks(db_session, "存在しないキーワード") == []


def test_station_idで絞り込める(db_session):
    result = search_chunks(db_session, "道の駅", station_id="P35_002")
    assert len(result) == 1
    assert result[0]["station_id"] == "P35_002"


def test_空クエリは空リスト(db_session):
    assert search_chunks(db_session, "   ") == []
