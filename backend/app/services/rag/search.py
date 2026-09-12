# FTS5全文検索サービス
# chunks_fts（app/db/session.pyのcreate_fts_tables参照）に対してMATCH検索を行い、
# 関連するチャンク本文を返す。ベクトル検索は行わない（DESIGN.mdの既知リスク対策どおり）。
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def search_chunks(
    db: Session,
    query: str,
    *,
    station_id: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """キーワードに関連するチャンクをFTS5検索で返す（関連度順）。

    queryはダブルクオートで囲みフレーズ検索として扱う。これによりFTS5クエリ構文の
    特殊文字（AND/OR/NOT等の予約語やハイフン）がユーザー入力にそのまま含まれても
    構文エラーにならない。

    注意: chunks_ftsはtokenize='trigram'（3文字単位のn-gram）を使うため、
    2文字以下のクエリはヒットしない（例: "名産"は0件、"名産品"は1件以上ヒットする）。
    """
    stripped = query.strip()
    if not stripped:
        return []

    fts_query = '"' + stripped.replace('"', '""') + '"'
    station_filter = "AND c.station_id = :station_id" if station_id else ""
    sql = text(
        f"""
        SELECT c.id, c.station_id, c.chunk_type, c.content
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        WHERE chunks_fts MATCH :q
        {station_filter}
        ORDER BY rank
        LIMIT :limit
        """
    )
    params: dict = {"q": fts_query, "limit": limit}
    if station_id:
        params["station_id"] = station_id

    rows = db.execute(sql, params).mappings().all()
    return [dict(row) for row in rows]
