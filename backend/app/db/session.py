# DB接続・セッション管理
# SQLiteのDBファイルは backend/data.db に作成する（.gitignoreの *.db で除外済み）
import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# このファイルは backend/app/db/session.py にあるので、
# 3階層上（backend/）に data.db を置く
DB_PATH = Path(os.environ.get("MICHI_DB_PATH") or (Path(__file__).resolve().parent.parent.parent / "data.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

# SQLiteはデフォルトで作成したスレッドからしか接続を使えない制約があるが、
# FastAPIはリクエストごとに異なるスレッドで動く可能性があるため check_same_thread=False とする。
# セッションはリクエスト単位（get_dbの中）で作成・破棄するので実害はない。
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# DBセッションを作るためのファクトリ
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """全SQLAlchemyモデル共通の基底クラス"""


def create_fts_tables(bind: Engine) -> None:
    """FTS5仮想テーブルを作成する（SQLAlchemy ORMはFTS5を直接扱えないためraw SQLを使う）。

    content='chunks', content_rowid='id' でchunksテーブルと紐付け、chunks_fts.rowidが
    そのままchunks.idになるようにする（検索結果からchunks行へJOINしやすくするため）。
    tokenize='trigram' を指定する（既定のunicode61は日本語のように単語間に空白が無い
    文章をひとつの巨大なトークンとして扱ってしまい、部分一致検索ができないため。
    trigramは3文字ごとのn-gramで分割するので形態素解析ライブラリ無しでも
    日本語の部分文字列検索が可能になる）。
    IF NOT EXISTSなので複数回呼んでも安全（init_db.py・テストのセットアップ両方から呼ばれる）。
    """
    with bind.begin() as conn:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    content,
                    content='chunks',
                    content_rowid='id',
                    tokenize='trigram'
                )
                """
            )
        )


def get_db() -> Session:
    """FastAPIの依存性注入(Depends)で使うDBセッション取得用関数。
    リクエスト処理が終わったら必ずセッションを閉じる。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
