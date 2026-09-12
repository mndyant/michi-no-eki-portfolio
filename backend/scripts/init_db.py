# DB初期化スクリプト
# backend/data.db に stations / clusters / station_distances / visit_records の
# 4テーブルを作成する。テーブルが既に存在する場合は何もしない（create_allは冪等）。
#
# 実行方法（backend/ ディレクトリで）:
#   .venv/Scripts/python.exe scripts/init_db.py
import sys
from pathlib import Path

# このスクリプトは backend/scripts/ にあるので、1階層上（backend/）を
# モジュール検索パスに追加し、"app" パッケージをimportできるようにする
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, create_fts_tables, engine  # noqa: E402
from app import models  # noqa: E402,F401  モデルをBase.metadataに登録するために必要


def main() -> None:
    """テーブルを作成し、作成されたテーブル名一覧を表示する"""
    Base.metadata.create_all(bind=engine)
    create_fts_tables(engine)  # chunks_fts（FTS5仮想テーブル）はORM管理外なので別途作成
    table_names = list(Base.metadata.tables.keys())
    print(f"テーブル作成完了（{len(table_names)}個）: {table_names}")
    print("chunks_fts（FTS5全文検索テーブル）も作成済み")


if __name__ == "__main__":
    main()
