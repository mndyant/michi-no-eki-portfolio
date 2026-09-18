# シード投入のDB反映ロジック（upsert方式）
#
# 背景（Issue #82）: 旧seed.pyは実行のたびにstations/clustersを全削除してから入れ直していたため、
# 再シードするたびに訪問フラグ・滞在時間カスタム・訪問記録・口コミ等のユーザーデータが消えていた。
# ここでは「シード由来フィールド」だけを更新し、ユーザーが編集したデータは一切触らないupsertを行う。
#
# app/services/seed_transform.py（純粋関数、DB非依存）が作った行データを受け取り、
# 実際のDB操作（INSERT/UPDATE、削除はしない）を担当する。DIでSessionを受け取るのでpytestで
# インメモリSQLiteを使ってテストできる。
#
# 既知の制限（レビューで確認済み・スコープ外として明記）:
# - 駅の「改名」だけは救えない。NOID_駅の仮IDは駅名由来のハッシュのため、改名すると
#   station_id・nameの両方が変わり別駅として新規INSERTされる（旧行はmissing_in_seed警告に載る）。
#   その場合は旧行のユーザーデータを手動で移す必要がある
# - NOID_駅に後から正式なGML ID（P35_xxx等）が付与されるケースも同様に自動では引き継げない
#   （下記_plan_station_matchesのドキュメント参照）。理由は改名と同じ「識別方式そのものが
#   変わる」ケースであり、station_id・nameどちらの単一シグナルでも安全に対応付けられない
#   ため。新規INSERT＋旧行はmissing_in_seedに残る形になり、手動での引き継ぎが必要
#   （なお、この昇格後の新IDが別の未対応既存駅の現IDと偶然一致する場合はSeedMatchConflictError
#   で中断する。衝突しない場合は例外にはならず、上記の通り静かに新規INSERT扱いになる）
# - GML由来ID同士の入れ替わり・循環、および識別子の種別変化を伴う同名衝突は検出しない
#   （詳細は_plan_station_matchesのドキュメント参照）。国土数値情報（P35）由来のIDが
#   手動で入れ替わる、または駅がGML登録の有無を行き来する、という現在の実データ運用
#   では起こり得ないシナリオと判断し、意図的にスコープ外とした（Issue #82レビュー5回目）
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.cluster import Cluster
from app.models.station import Station
from app.models.station_distance import StationDistance
from app.services.seed_transform import build_business_hours_json

# business_hours関連フィールドの「シードのデフォルト仮値」。
# DBの現在値が4項目すべてこれらと一致する場合のみ上書きする（1つでも異なればユーザーが
# 手動確認して変更した可能性があるため、4項目とも触らない＝ユーザー入力を優先する）
DEFAULT_BUSINESS_HOURS_JSON = build_business_hours_json()
DEFAULT_STAMP_START = "09:00"
DEFAULT_STAMP_END = "17:00"
DEFAULT_CLOSED_DAYS = ""

# 既存駅を更新する際、常に上書きしてよい「シード由来フィールド」。
# 座標・住所・施設情報など、ユーザーが編集する余地の無い基本データのみを対象にする。
# visited / visited_date / stay_time_min_default / reputation_items / user_memo /
# local_specialty / seasonal_specialty / scenery_score はユーザー編集フィールドのため
# ここには含めない（新規駅INSERT時のみ初期値が入り、既存駅の更新では一切触らない）。
# station_id はUNIQUE制約があり衝突回避の二段階更新が必要なため、ここではなく
# upsert_stations内で個別に扱う
ALWAYS_UPDATE_FIELDS = (
    "name",
    "pref",
    "city",
    "address",
    "lat",
    "lon",
    "official_url",
    "facility_scale",
    "good_for_lunch",
    "good_for_sweets",
    "good_for_souvenir",
    "has_spa",
    "is_mountainous",
    "revisit_difficulty_score",
    "revisit_difficulty_reason",
    "source",
    "last_verified_at",
)


class SeedMatchConflictError(Exception):
    """upsertの事前マッチングで、シード行と既存駅の対応関係が一意に決まらなかった場合に送出する。

    背景（Issue #82レビュー4回目）: レビュー3回目で「station_id一致→name一致」の
    事前一括マッチングに直したが、それでもなお「station_id一致判定が“既存行が現在その
    IDを持っているか”というフィールド内容の一致でしかなく、駅の実体（同一性）の判定に
    なっていない」という根本原因が残っていた。NOID_駅同士でstation_idの中身が入れ替わる
    ケース（例: 駅Bのシード行のtarget IDが、たまたま駅A側の現station_idと一致する）で、
    station_id一致検索が別駅を誤って掴んでしまい、SeedMatchConflictErrorも発生せずに
    ユーザーデータが意味的に入れ替わる実害がCodexレビューで再現された。

    レビュー4回目でマッチング規則そのものを再設計し（_plan_station_matches参照）、
    NOID_駅とGML由来駅で識別キーの種類を完全に分離した結果、この種の衝突は構造的に
    起きにくくなったが、それでも真に解決不能な衝突（シード内でのtarget station_id重複、
    station_id方式とname方式のマッチが同じ既存駅を指してしまう等）は依然としてありえる。
    黙って誤マッチさせるより、対応関係が一意に決まらない時点で更新を一切行わず中断する方が
    安全なため、ここでfail-fastする（呼び出し元でcommitされていなければDB変更は残らない）。
    """


@dataclass
class SeedUpsertResult:
    """upsert結果のサマリ（seed.py側の表示・検証用）"""

    inserted: list[str] = field(default_factory=list)  # 新規投入したstation_id一覧
    updated: list[str] = field(default_factory=list)  # 更新した既存駅のstation_id一覧
    # シードに存在しないがDBに残っている駅（削除はしない。呼び出し側で警告表示する）
    missing_in_seed: list[str] = field(default_factory=list)
    # 座標変更に伴い失効させた駅間距離キャッシュ（station_distances）の行数
    distance_cache_invalidated: int = 0


def upsert_clusters(db: Session, cluster_rows: list[dict]) -> dict[str, int]:
    """クラスタをupsertし、クラスタ名→DB上のidの対応表を返す。

    既存クラスタは削除しない（description等をユーザーが手動編集している可能性があるため）。
    シードに同名クラスタがあれば流用し、無ければ新規作成するだけに留める。

    既知の制限（スコープ外）: クラスタ名は「府県名+入力順の連番」（例: 大阪府1）のため、
    シードデータの並び替えやクラスタ構成の変化によって、同じ名前が以前とは別の実体
    （別の駅集合）を指す可能性がある。名前一致で流用する本実装では意味的な安定性までは
    保証しない。クラスタへの安定ID付与は別Issueで扱う
    """
    existing_by_name = {cluster.name: cluster for cluster in db.query(Cluster).all()}
    cluster_id_by_name: dict[str, int] = {}

    for row in cluster_rows:
        cluster = existing_by_name.get(row["name"])
        if cluster is None:
            cluster = Cluster(name=row["name"], description=row.get("description"))
            db.add(cluster)
            db.flush()  # このあとの駅投入でidを参照できるようにする
        cluster_id_by_name[row["name"]] = cluster.id

    return cluster_id_by_name


def _business_hours_all_default(station: Station) -> bool:
    """business_hours系4項目がすべてシードのデフォルト仮値のままかを判定する"""
    return (
        station.business_hours == DEFAULT_BUSINESS_HOURS_JSON
        and station.stamp_start == DEFAULT_STAMP_START
        and station.stamp_end == DEFAULT_STAMP_END
        and station.closed_days == DEFAULT_CLOSED_DAYS
    )


def _apply_business_hours_fields(station: Station, row: dict) -> None:
    """business_hours/stamp_start/stamp_end/closed_daysの更新（グループ判定）。

    4項目のうち1つでもデフォルト仮値と異なれば「ユーザーが手動確認済み」とみなし、
    4項目すべてを保護して何も上書きしない（項目ごとに個別判定すると、closed_daysだけ
    直したユーザーの他3項目がシード値で上書きされて混合状態になるため）。
    「手動確認した結果が偶然デフォルト値と同じだった」ケースは救えないが、その恒久対応
    （hours_verified_atカラムの追加による明示的な確認済み管理）は営業時間の実データ化
    作業（Issue #71系の続き）に委ねる
    """
    if not _business_hours_all_default(station):
        return
    station.business_hours = row["business_hours"]
    station.stamp_start = row["stamp_start"]
    station.stamp_end = row["stamp_end"]
    station.closed_days = row["closed_days"]


def _invalidate_distance_cache(db: Session, station_pks: list[int]) -> int:
    """座標が変わった駅の駅間距離キャッシュ（station_distances）を削除する。

    座標が変わると既存のキャッシュ値（距離・移動時間）が実態と合わなくなるため、
    from/toのいずれかが該当駅である行を同一トランザクション内で失効させる。
    戻り値は削除した行数
    """
    if not station_pks:
        return 0
    return (
        db.query(StationDistance)
        .filter(
            or_(
                StationDistance.from_station_id.in_(station_pks),
                StationDistance.to_station_id.in_(station_pks),
            )
        )
        .delete(synchronize_session=False)
    )


def _check_no_duplicate_seed_target_ids(station_rows: list[dict]) -> None:
    """シード行同士でtarget station_idが重複していないかを検査する（Issue #82レビュー4回目・P2）。

    既存DBとの照合より前の、シードデータ単体の整合性チェック。DB未登録の新規行同士
    （どちらも既存駅と一致しない）であっても、2行が同じstation_idを名乗っていれば
    後続のINSERTでUNIQUE制約違反になる、またはそもそもシード生成ロジックの不具合の
    兆候なので、既存駅との照合を試みる前にここで検出して中断する。
    """
    seen_at: dict[str, int] = {}
    for idx, row in enumerate(station_rows):
        target_id = row["station_id"]
        if target_id in seen_at:
            other_row = station_rows[seen_at[target_id]]
            raise SeedMatchConflictError(
                "シードデータ内でstation_idが重複しています。"
                f"station_id「{target_id}」がシード行「{other_row['name']}」と"
                f"シード行「{row['name']}」の両方に付与されています。"
                "app/services/seed_transform.py（駅IDの割当ロジック）またはdata/raw/"
                "stations_kinki.json を確認してください。"
            )
        seen_at[target_id] = idx


def _plan_station_matches(
    existing_stations: list[Station], station_rows: list[dict]
) -> dict[int, Station]:
    """シード行と既存駅の対応関係を「全行一括」で確定する（処理順序に依存しない）。

    背景（Issue #82レビュー4回目）: レビュー3回目までは「station_id一致→name一致」を
    優先順位付きフォールバックとして両方の行に適用していたが、これだと根本原因（Codexが
    指摘: 「station_id一致判定が“既存行が現在そのIDを持っているか”というフィールド内容の
    一致でしかなく、駅の実体（同一性）の判定になっていない」）が解消されておらず、
    NOID_駅同士でstation_idの中身が入れ替わるケースで、SeedMatchConflictErrorすら
    発生せずに別駅のデータへ誤って書き込んでしまう実害が再現された。

    そこで、駅の識別キーをIDの種類によって完全に分離する設計に変更した:
      1. シード行のtarget station_idが"NOID_"で始まらない場合（GML由来の正式ID、
         例: P35_xxx）: 既存行との一致判定はstation_id一致のみで行う。GML IDは
         安定的でシード間で変わらない前提のため、これで正しい
      2. シード行のtarget station_idが"NOID_"で始まる場合: 既存行との一致判定は
         name一致のみで行う（station_idフィールドの中身は一切見ない）。NOID_は
         名前ハッシュから機械的に導出される値であり、「今そのIDを持っている行」を
         探すこと自体が同一性判定として誤り。名前こそが、プレースホルダー駅の実体を
         表す唯一の信頼できるキー

    この設計により、station_idフィールドの値がどう入れ替わろうと、NOID行の同一性判定は
    常にnameだけを見るため、レビュー4回目で再現された「station_idの取り違え」は構造的に
    起きなくなる。さらに、ID方式(1)のみ・name方式(2)のみで見る限り、既存駅のstation_id
    （またはname）はDB上でUNIQUE/名前一意フィルタ済みのため、単独の方式では複数のシード
    行が同じ既存駅を指すことは原理的に起こらない（duplicate target idの事前チェックと
    組み合わせれば、ID方式のみ・name方式のみのローテーション/入れ替えは常に安全に解決
    できる）。衝突が起こりうるのは以下のケースのみ:
      - シード内でtarget station_idそのものが重複している（_check_no_duplicate_seed_target_idsで
        既存駅照合の前に検出）
      - ID方式で一致した行とname方式で一致した行が、同じ既存駅を指してしまうケース
        （＝GML由来駅とNOID_駅の間で識別方式をまたいだ衝突。どちらが正しい対応か機械的に
        判定できないため中断する）
      - あるシード行のtarget station_idが、このシードでは対応が見つからず更新されない
        （＝現在のIDのままDBに残り続ける）別の既存駅のIDと一致してしまうケース
        （典型例: NOID_駅Aが正式GML IDに昇格し、NOID_駅Bが駅Aの旧IDを引き継ごうとするが、
        駅Aの旧行はどのシード行からも一致されず未更新のまま残るため、駅Bの新IDと衝突する）
      - 既存DBに同名駅が複数あり、その名前を頼りに照合しようとするNOID_行が現れるケース
        （Issue #82レビュー5回目・ブロッカー3）。同名が2件以上あるとname一致では
        どちらに対応するのか機械的に判定できないため、単に索引から除外して「一致なし」
        （＝新規INSERT）扱いにすると、初回投入は成功するが2回目以降は新規行の
        station_idが既存行と衝突して失敗する非冪等な挙動になってしまう。そのため、
        該当名を頼りに実際に照合を試みるNOID_行が現れた時点で中断する

    既知の制限: 駅の「改名」、および「NOID_駅への正式GML ID付与」は、識別方式そのものが
    変わる（name一致からID一致に切り替わる、またはその逆）ため自動では対応付けられない。
    どちらも別駅として新規INSERTされ、旧行は削除されずmissing_in_seedに載る
    （手動でのユーザーデータ引き継ぎが必要）。

    既知の制限（Issue #82レビュー5回目で検討の上、意図的にスコープ外とした）:
      - GML由来ID同士の入れ替わり・循環（例: 既存P35_100とP35_200のstation_idが
        シード側で入れ替わって投入される）は検出しない。rule 1（station_id一致のみ）は
        各既存駅のIDと1対1で対応付くため、たまたま値が入れ替わっていても「別の駅の
        現在のデータ」としてではなく「そのIDを持つ行の更新」として処理されてしまう
      - GML⇔NOID間で識別子の種別が変わり、かつ同名の別駅が絡む衝突は、上記の
        「ID方式で一致した行とname方式で一致した行が同じ既存駅を指すケース」以外は
        検出しない（例えば、GML行の一致判定はstation_idのみを見るため、name重複が
        あってもGML側では衝突として気づけない）
      これらは国土数値情報（P35）由来のIDが手動で入れ替わる、または駅がGML登録の
      有無を行き来する、という現在の実データ運用では起こり得ないシナリオと判断し
      （2026-05-17時点の159駅データにはこれらの前提を崩すケースは存在しない）、
      検出コストに見合わないため意図的に実装していない。将来、シードデータの性質が
      変わった場合は本docstringを再検討すること。

    戻り値: {シード行のインデックス: 対応する既存Station}
    """
    _check_no_duplicate_seed_target_ids(station_rows)

    existing_by_station_id = {s.station_id: s for s in existing_stations}
    # nameマッチ用の対応表。同名駅が複数ある場合はどれに紐付くか判定できないため、
    # 名前が一意な駅だけを対象にする。ただし単に索引から除外するだけだと、その名前を
    # 持つNOID_行が「一致なし」＝新規INSERT扱いになってしまい、初回投入は成功するが
    # 2回目以降は新規行のstation_idが既存行と衝突してUNIQUE制約違反になる、という
    # 非冪等な状態を生む（Issue #82レビュー5回目・ブロッカー3）。そのため、除外した
    # 名前はambiguous_namesに記録しておき、実際にその名前を頼りに照合を試みるNOID_行が
    # 現れた時点でSeedMatchConflictErrorを送出する（「対応が一意に決まらないなら中断」
    # という既存方針の単純な拡張）
    name_counts: dict[str, int] = {}
    for s in existing_stations:
        name_counts[s.name] = name_counts.get(s.name, 0) + 1
    existing_by_name = {s.name: s for s in existing_stations if name_counts[s.name] == 1}
    ambiguous_names = {name for name, count in name_counts.items() if count > 1}

    matches: dict[int, Station] = {}
    # 既存駅PK -> (それを確保したシード行のインデックス, 確保した理由)。衝突検出に使う
    claimed_by: dict[int, tuple[int, str]] = {}

    def claim(idx: int, station: Station, reason: str) -> None:
        if station.id in claimed_by:
            other_idx, other_reason = claimed_by[station.id]
            other_row = station_rows[other_idx]
            row = station_rows[idx]
            raise SeedMatchConflictError(
                "シード投入の事前マッチングで対応関係が一意に決まりませんでした。"
                f"既存駅「{station.name}」（現station_id={station.station_id}）が、"
                f"シード行「{other_row['name']}」（新station_id={other_row['station_id']}、"
                f"{other_reason}）と"
                f"シード行「{row['name']}」（新station_id={row['station_id']}、{reason}）の"
                "両方から一致してしまっています。"
                "シードデータ（data/raw/stations_kinki.json）またはDBの該当駅を手動で"
                "確認し、station_idの重複・入れ替わりを解消してから再実行してください。"
            )
        claimed_by[station.id] = (idx, reason)
        matches[idx] = station

    # NOID_行はnameのみ、それ以外（GML由来ID）の行はstation_idのみで既存駅を探す。
    # 1回の走査で全行に対して確定できる（優先順位付きフォールバックではなく、
    # 行ごとに使う判定方式そのものが最初から一意に決まっているため）
    for idx, row in enumerate(station_rows):
        if row["station_id"].startswith("NOID_"):
            if row["name"] in ambiguous_names:
                # 既存DBに同名駅が複数あり、どちらに対応するシード行なのか機械的に
                # 判定できない（Issue #82レビュー5回目・ブロッカー3）
                dup_count = name_counts[row["name"]]
                raise SeedMatchConflictError(
                    f"シード行「{row['name']}」（新station_id={row['station_id']}）は"
                    "name一致で既存駅と対応付けようとしていますが、"
                    f"既存DBに同名「{row['name']}」の駅が{dup_count}件あり、"
                    "どちらに対応するのか一意に判定できません。"
                    "DBの該当駅（station_idが異なる同名レコード）を手動で確認し、"
                    "重複の解消（統合・改名等）をしてから再実行してください。"
                )
            candidate = existing_by_name.get(row["name"])
            reason = "name一致（NOID_行のためstation_idフィールドの中身は見ない）"
        else:
            candidate = existing_by_station_id.get(row["station_id"])
            reason = "station_id一致（GML由来ID）"
        if candidate is not None:
            claim(idx, candidate, reason)

    # 追加チェック: マッチしなかった（＝このシードでは一切更新されず、現在のstation_idの
    # ままDBに残り続ける）既存駅のIDを、いずれかのシード行が新しいstation_idとして
    # 名乗っていないか。name一致で照合される行はstation_idフィールドの中身を見ないため、
    # 「別の駅（このシードでは対応が見つからない駅）が今まさに使っているID」を偶然
    # 目標IDにしてしまう組み合わせがありうる。これを見逃すと、この関数自体は正常終了して
    # しまい、実際のUPDATE/INSERT時にSQLiteのUNIQUE制約違反という分かりにくい形で
    # 失敗する（＝fail-fastの意図に反する）ため、ここで検出して中断する
    matched_pks = {station.id for station in matches.values()}
    unmatched_existing_ids = {
        s.station_id for s in existing_stations if s.id not in matched_pks
    }
    for idx, row in enumerate(station_rows):
        target_id = row["station_id"]
        if target_id in unmatched_existing_ids:
            colliding = next(
                s for s in existing_stations if s.station_id == target_id and s.id not in matched_pks
            )
            raise SeedMatchConflictError(
                f"シード行「{row['name']}」（新station_id={target_id}）が、"
                f"このシードでは対応する行が見つからず更新されない既存駅"
                f"「{colliding.name}」（station_id={target_id}）と同じstation_idを"
                "使おうとしています。このまま投入するとstation_idの重複が発生するため中断します。"
                "シードデータ（data/raw/stations_kinki.json）またはDBの該当駅を手動で"
                "確認してください。"
            )

    return matches


def upsert_stations(
    db: Session,
    station_rows: list[dict],
    cluster_id_by_name: dict[str, int],
    existing_stations: list[Station] | None = None,
    match_plan: dict[int, Station] | None = None,
) -> SeedUpsertResult:
    """駅をupsertする。既存駅との対応付けは_plan_station_matches（station_id方式と
    name方式を駅IDの種類で完全に分離した設計。詳細はそちらのdocstring参照）で行う。

    対応関係の確定は全行一括かつ処理順序に依存しない方式で行い、一意に決まらない場合は
    SeedMatchConflictErrorで処理全体を中断する（部分的な書き込みをしない。呼び出し側で
    commitしていなければDBへの変更は残らない）。

    existing_stations/match_planは省略可（省略時はこの関数内で計算する）。run_seedからは
    トランザクション安全性のため事前に計算済みのものを渡す（クラスタupsertより前に
    マッチング検証を済ませたいため。詳細はrun_seedのdocstring参照）。

    既存駅の更新はALWAYS_UPDATE_FIELDS + business_hours系（グループ判定）のみ。
    visited等のユーザー編集フィールドには一切触れない。
    シードから消えた駅は削除せず残す（結果のmissing_in_seedに記録する）。
    lat/lonが実際に変わった駅は駅間距離キャッシュ（station_distances）を失効させる。
    station_idの付け替えはUNIQUE制約違反を避けるため「対象行を一時IDへ退避→正式IDへ
    確定」の二段階更新で行う（旧NOID同士でIDが入れ替わるようなケースでも安全）。
    """
    if existing_stations is None:
        existing_stations = db.query(Station).all()
    if match_plan is None:
        match_plan = _plan_station_matches(existing_stations, station_rows)
    matched_pks = {station.id for station in match_plan.values()}

    result = SeedUpsertResult()
    station_id_changes: list[tuple[Station, str]] = []  # 二段階更新の対象（駅, 新station_id）
    moved_station_pks: list[int] = []  # 座標が変わった駅のPK（距離キャッシュ失効用）

    for idx, row in enumerate(station_rows):
        cluster_name = row.get("cluster_name")
        cluster_id = cluster_id_by_name.get(cluster_name) if cluster_name else None
        station = match_plan.get(idx)

        if station is None:
            # 新規駅：cluster_nameを除いた全フィールドをそのまま投入する
            insert_data = {k: v for k, v in row.items() if k != "cluster_name"}
            db.add(Station(cluster_id=cluster_id, **insert_data))
            result.inserted.append(row["station_id"])
            continue

        # 座標変更の検出は更新前に行う（更新後では比較できないため）
        if (station.lat, station.lon) != (row["lat"], row["lon"]):
            moved_station_pks.append(station.id)

        for field_name in ALWAYS_UPDATE_FIELDS:
            setattr(station, field_name, row[field_name])
        _apply_business_hours_fields(station, row)
        station.cluster_id = cluster_id

        # station_idの付け替え（NOID_駅がname一致で照合された場合等）は即時反映せず、
        # 全行の処理後に二段階更新でまとめて行う
        if station.station_id != row["station_id"]:
            station_id_changes.append((station, row["station_id"]))
        result.updated.append(row["station_id"])

    # station_idの二段階更新: 新IDが「他の行が現在保持しているID」と一時的に衝突しても
    # UNIQUE制約違反にならないよう、まず対象行を衝突しえない一時IDへ退避してから確定させる
    if station_id_changes:
        for station, _ in station_id_changes:
            station.station_id = f"__SEED_TMP__{station.id}"
        db.flush()
        for station, new_station_id in station_id_changes:
            station.station_id = new_station_id
        db.flush()

    result.distance_cache_invalidated = _invalidate_distance_cache(db, moved_station_pks)

    result.missing_in_seed = [s.station_id for s in existing_stations if s.id not in matched_pks]

    return result


def run_seed(
    db: Session, station_rows: list[dict], cluster_rows: list[dict]
) -> SeedUpsertResult:
    """クラスタ→駅の順でupsertし、commitまで行う（seed.pyから呼び出すエントリポイント）。

    トランザクション安全性（Issue #82レビュー4回目・P2指摘）: 以前はupsert_clusters()を
    先に呼んでいたが、これは新規クラスタをdb.flush()で先行的にDBへ書き込む（コミット前
    ではあるが、同一トランザクション内に変更が積まれる）。もし駅側のマッチング検証で
    衝突が見つかりSeedMatchConflictErrorが送出された場合、呼び出し側の実装によっては
    クラスタの変更だけが誤ってcommitされてしまう恐れがあった。
    そのため、駅の対応関係の確定・衝突検証（_plan_station_matches）を**クラスタのupsert
    より前**に行う順序に変更した。これにより、駅側で衝突が見つかった場合はクラスタへの
    書き込みが一切発生する前に処理を中断できる。
    さらに、本関数全体をtry/exceptで包み、どの段階で例外が飛んでもdb.rollback()してから
    再送出する。これにより、呼び出し側がdb.commit()を呼ばない実装であっても
    （SQLAlchemyのSession.close()は未コミットの変更を破棄するため通常は問題にならないが）
    確実にトランザクションが破棄されることを保証する。
    """
    try:
        existing_stations = db.query(Station).all()
        # 駅の対応関係を先に確定・検証する（クラスタへの書き込みより前）。
        # ここで得たmatch_planはそのままupsert_stationsへ渡し、二重計算を避ける
        match_plan = _plan_station_matches(existing_stations, station_rows)

        cluster_id_by_name = upsert_clusters(db, cluster_rows)
        result = upsert_stations(
            db,
            station_rows,
            cluster_id_by_name,
            existing_stations=existing_stations,
            match_plan=match_plan,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
