# app/services/seed_service.py の単体テスト（Issue #82: 全削除→upsert方式への恒久修正）
#
# インメモリSQLiteに「訪問済み・カスタム滞在時間・訪問記録・口コミ」を持つ駅を用意し、
# 再シード（upsert_stations/run_seed）を実行してもユーザーデータが保持されること、
# シード由来フィールドの更新・新規駅のINSERT・消えた駅の非削除を検証する。
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base  # noqa: E402
from app.models.cluster import Cluster  # noqa: E402
from app.models.station import Station  # noqa: E402
from app.models.station_distance import StationDistance  # noqa: E402
from app.models.visit_record import VisitRecord  # noqa: E402
from app.services.seed_service import (  # noqa: E402
    DEFAULT_BUSINESS_HOURS_JSON,
    SeedMatchConflictError,
    SeedUpsertResult,
    run_seed,
    upsert_clusters,
    upsert_stations,
)
from app.services.seed_transform import (  # noqa: E402
    build_placeholder_station_id,
    transform_stations,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)
    session = testing_session()
    yield session
    session.close()


def _make_seed_station_row(
    station_id: str = "P35_001",
    name: str = "道の駅テスト",
    pref: str = "大阪府",
    lat: float = 34.70,
    lon: float = 135.50,
    cluster_name: str | None = None,
) -> dict:
    """upsert_stationsへ渡す1駅分のシード行データ（transform_stationsの出力相当）を作る"""
    return {
        "station_id": station_id,
        "name": name,
        "pref": pref,
        "city": None,
        "address": "大阪市北区1-1",
        "lat": lat,
        "lon": lon,
        "official_url": "https://example.com",
        "business_hours": DEFAULT_BUSINESS_HOURS_JSON,
        "stamp_start": "09:00",
        "stamp_end": "17:00",
        "closed_days": "",
        "visited": False,
        "visited_date": None,
        "stay_time_min_default": 15,
        "facility_scale": "small",
        "good_for_lunch": False,
        "good_for_sweets": False,
        "good_for_souvenir": False,
        "has_spa": False,
        "scenery_score": None,
        "is_mountainous": False,
        "revisit_difficulty_score": 1,
        "revisit_difficulty_reason": "基準1点のみ（加点要因なし）。",
        "cluster_name": cluster_name,
        "reputation_items": "[]",
        "local_specialty": "[]",
        "seasonal_specialty": "[]",
        "user_memo": None,
        "source": "国土数値情報+Wikipedia(2026-05-17)",
        "last_verified_at": date(2026, 5, 17),
    }


def _add_existing_station(db, **overrides) -> Station:
    defaults = dict(
        station_id="P35_001",
        name="道の駅テスト",
        pref="大阪府",
        city=None,
        address="旧住所",
        lat=34.0,
        lon=135.0,
        official_url=None,
        business_hours=DEFAULT_BUSINESS_HOURS_JSON,
        stamp_start="09:00",
        stamp_end="17:00",
        closed_days="",
        visited=False,
        visited_date=None,
        stay_time_min_default=15,
        facility_scale="small",
        good_for_lunch=False,
        good_for_sweets=False,
        good_for_souvenir=False,
        has_spa=False,
        scenery_score=None,
        is_mountainous=False,
        revisit_difficulty_score=1,
        revisit_difficulty_reason="旧理由",
        cluster_id=None,
        reputation_items="[]",
        local_specialty="[]",
        seasonal_specialty="[]",
        user_memo=None,
        source="旧ソース",
        last_verified_at=date(2020, 1, 1),
    )
    defaults.update(overrides)
    station = Station(**defaults)
    db.add(station)
    db.commit()
    return station


def test_upsert_preserves_user_data_on_existing_station(db_session):
    """(a) 訪問済み・カスタム滞在時間・口コミ・訪問記録は再シードしても保持される"""
    station = _add_existing_station(
        db_session,
        visited=True,
        visited_date=date(2026, 6, 1),
        stay_time_min_default=45,
        reputation_items='["景色が良い"]',
        user_memo="また行きたい",
        local_specialty='["みかん"]',
        seasonal_specialty='["いちご"]',
        scenery_score=5,
    )
    db_session.add(
        VisitRecord(
            station_id=station.id,
            visit_date=date(2026, 6, 1),
            purchased_items='["梅干し"]',
            food="[]",
            impression="良かった",
        )
    )
    db_session.commit()

    row = _make_seed_station_row(lat=34.9, lon=135.9)  # 座標を変えたシードデータ
    result = upsert_stations(db_session, [row], {})
    db_session.commit()

    refreshed = db_session.query(Station).filter_by(station_id="P35_001").one()
    assert refreshed.visited is True
    assert refreshed.visited_date == date(2026, 6, 1)
    assert refreshed.stay_time_min_default == 45
    assert refreshed.reputation_items == '["景色が良い"]'
    assert refreshed.user_memo == "また行きたい"
    assert refreshed.local_specialty == '["みかん"]'
    assert refreshed.seasonal_specialty == '["いちご"]'
    assert refreshed.scenery_score == 5

    # 訪問記録は削除されず、station_id（内部PK）で紐づいたまま残る
    records = db_session.query(VisitRecord).filter_by(station_id=refreshed.id).all()
    assert len(records) == 1
    assert records[0].impression == "良かった"

    assert result.updated == ["P35_001"]
    assert result.inserted == []


def test_upsert_updates_seed_owned_fields(db_session):
    """(b) 座標・住所などシード由来フィールドは新しい値に更新される"""
    _add_existing_station(db_session, lat=34.0, lon=135.0, address="旧住所")

    row = _make_seed_station_row(lat=34.9, lon=135.9)
    row["address"] = "新住所"
    upsert_stations(db_session, [row], {})
    db_session.commit()

    refreshed = db_session.query(Station).filter_by(station_id="P35_001").one()
    assert refreshed.lat == 34.9
    assert refreshed.lon == 135.9
    assert refreshed.address == "新住所"


def test_upsert_does_not_overwrite_manually_edited_business_hours(db_session):
    """business_hours等は、DBの値がデフォルト仮値と異なる＝手動編集済みとみなして上書きしない"""
    _add_existing_station(
        db_session,
        business_hours='{"mon": "10:00-16:00"}',
        stamp_start="10:00",
        stamp_end="16:00",
        closed_days="水曜日",
    )

    row = _make_seed_station_row()  # デフォルト仮値（09:00-17:00等）
    upsert_stations(db_session, [row], {})
    db_session.commit()

    refreshed = db_session.query(Station).filter_by(station_id="P35_001").one()
    assert refreshed.business_hours == '{"mon": "10:00-16:00"}'
    assert refreshed.stamp_start == "10:00"
    assert refreshed.stamp_end == "16:00"
    assert refreshed.closed_days == "水曜日"


def test_upsert_updates_business_hours_when_still_default(db_session):
    """DBの値がデフォルト仮値のままなら、シード側の値で更新してよい"""
    _add_existing_station(db_session)  # business_hours等はデフォルトのまま

    row = _make_seed_station_row()
    row["stamp_start"] = "08:30"
    upsert_stations(db_session, [row], {})
    db_session.commit()

    refreshed = db_session.query(Station).filter_by(station_id="P35_001").one()
    assert refreshed.stamp_start == "08:30"


def test_upsert_protects_all_four_hours_fields_when_only_closed_days_edited(db_session):
    """closed_daysだけをユーザーが手動修正した場合でも、グループ判定により
    business_hours/stamp_start/stamp_end/closed_daysの4項目すべてが保護される
    （個別判定だと他3項目がシード値で上書きされ混合状態になってしまうのを防ぐ）
    """
    _add_existing_station(
        db_session,
        business_hours=DEFAULT_BUSINESS_HOURS_JSON,  # 他3項目はデフォルトのまま
        stamp_start="09:00",
        stamp_end="17:00",
        closed_days="水曜日",  # ここだけユーザーが手動修正
    )

    row = _make_seed_station_row()  # シード側は全項目デフォルト仮値
    row["stamp_start"] = "08:00"  # シード側に変化があっても上書きされないことを確認
    upsert_stations(db_session, [row], {})
    db_session.commit()

    refreshed = db_session.query(Station).filter_by(station_id="P35_001").one()
    # closed_days以外もデフォルト値のままシードで上書きされず保護されている
    assert refreshed.business_hours == DEFAULT_BUSINESS_HOURS_JSON
    assert refreshed.stamp_start == "09:00"
    assert refreshed.stamp_end == "17:00"
    assert refreshed.closed_days == "水曜日"


def test_upsert_invalidates_distance_cache_when_coords_change(db_session):
    """座標が実際に変わった駅は、station_distancesの関連行（from/toどちらでも）が
    同一トランザクション内で削除される
    """
    moved = _add_existing_station(
        db_session, station_id="P35_001", name="移動駅", lat=34.0, lon=135.0
    )
    unmoved = _add_existing_station(
        db_session, station_id="P35_002", name="不動駅", lat=35.0, lon=136.0
    )
    db_session.add(
        StationDistance(
            from_station_id=moved.id,
            to_station_id=unmoved.id,
            distance_km=10.0,
            duration_min=15.0,
            source="haversine",
            updated_at=datetime(2026, 1, 1),
        )
    )
    db_session.add(
        StationDistance(
            from_station_id=unmoved.id,
            to_station_id=unmoved.id,
            distance_km=0.0,
            duration_min=0.0,
            source="haversine",
            updated_at=datetime(2026, 1, 1),
        )
    )
    db_session.commit()

    rows = [
        _make_seed_station_row(station_id="P35_001", name="移動駅", lat=34.9, lon=135.9),
        _make_seed_station_row(station_id="P35_002", name="不動駅", lat=35.0, lon=136.0),
    ]
    result = upsert_stations(db_session, rows, {})
    db_session.commit()

    assert result.distance_cache_invalidated == 1
    remaining = db_session.query(StationDistance).all()
    assert len(remaining) == 1
    assert remaining[0].from_station_id == unmoved.id
    assert remaining[0].to_station_id == unmoved.id


def test_upsert_inserts_new_station(db_session):
    """(c) シードにあってDBに無い駅は新規INSERTされる"""
    row = _make_seed_station_row(station_id="P35_002", name="新規道の駅")
    result = upsert_stations(db_session, [row], {})
    db_session.commit()

    assert result.inserted == ["P35_002"]
    inserted = db_session.query(Station).filter_by(station_id="P35_002").one()
    assert inserted.name == "新規道の駅"
    assert inserted.visited is False


def test_upsert_does_not_delete_stations_missing_from_seed(db_session):
    """(d) DBにあってシードから消えた駅は削除せず、missing_in_seedに記録するだけ"""
    _add_existing_station(db_session, station_id="P35_001", name="残存駅")

    # シードには別の駅だけが含まれる（P35_001は消えた想定）
    row = _make_seed_station_row(station_id="P35_999", name="別の駅")
    result = upsert_stations(db_session, [row], {})
    db_session.commit()

    still_there = db_session.query(Station).filter_by(station_id="P35_001").one_or_none()
    assert still_there is not None
    assert result.missing_in_seed == ["P35_001"]


def test_upsert_migrates_old_positional_noid_to_hash_id(db_session):
    """旧形式の位置連番NOID（NOID_001等）が入った既存DBからの移行。
    station_idではヒットしないがnameフォールバックで照合され、
    station_idが新しいハッシュIDに更新されつつユーザーデータは保持される
    """
    _add_existing_station(
        db_session, station_id="NOID_003", name="無名駅", visited=True, stay_time_min_default=99
    )

    new_hash_id = build_placeholder_station_id("無名駅")
    row = _make_seed_station_row(station_id=new_hash_id, name="無名駅", lat=99.0, lon=99.0)
    result = upsert_stations(db_session, [row], {})
    db_session.commit()

    assert result.updated == [new_hash_id]
    assert result.inserted == []
    assert result.missing_in_seed == []
    refreshed = db_session.query(Station).filter_by(name="無名駅").one()
    # nameで同一視されて更新扱いになり、station_idはハッシュIDに移行されるが
    # ユーザーデータ（visited/stay_time_min_default）は保持される
    assert refreshed.station_id == new_hash_id
    assert refreshed.visited is True
    assert refreshed.stay_time_min_default == 99
    assert refreshed.lat == 99.0


def test_upsert_migrates_multiple_old_noids_without_unique_violation(db_session):
    """旧形式NOID_001〜が複数入ったDBの一括移行でUNIQUE制約違反が起きないこと"""
    _add_existing_station(db_session, station_id="NOID_001", name="無名駅A", visited=True)
    _add_existing_station(db_session, station_id="NOID_002", name="無名駅B", visited=True)

    rows = [
        _make_seed_station_row(
            station_id=build_placeholder_station_id("無名駅A"), name="無名駅A"
        ),
        _make_seed_station_row(
            station_id=build_placeholder_station_id("無名駅B"), name="無名駅B"
        ),
    ]
    result = upsert_stations(db_session, rows, {})
    db_session.commit()

    assert result.inserted == []
    assert result.missing_in_seed == []
    a = db_session.query(Station).filter_by(name="無名駅A").one()
    b = db_session.query(Station).filter_by(name="無名駅B").one()
    assert a.station_id == build_placeholder_station_id("無名駅A")
    assert b.station_id == build_placeholder_station_id("無名駅B")
    assert a.visited is True
    assert b.visited is True


def test_upsert_noid_id_swap_resolves_correctly_via_name_only_matching(db_session):
    """Issue #82レビュー4回目・Codexが実際に再現したバグの回帰テスト。

    既存PK1(station_id=NOID_002, name=駅B, 滞在88)、既存PK2(station_id=NOID_001, name=駅A,
    滞在77)に対し、シードで「駅B→NOID_001」「駅A→NOID_002」（station_idの中身が入れ替わる
    ようなtarget）を投入する。旧実装（レビュー3回目まで）はstation_id一致検索が「現在
    NOID_001を持つ行」＝駅Aを"駅Bのシード行の一致先"として誤って掴んでしまい、
    SeedMatchConflictErrorも発生しないまま駅Aと駅Bの滞在時間が意味的に入れ替わっていた。

    レビュー4回目の再設計後は、target station_idがNOID_で始まる行はstation_idフィールドの
    中身を一切見ずname一致のみで既存行を探すため、station_idの値がどう入れ替わっていても
    「駅B」という名前のシード行は必ず既存の駅B（PK1）に、「駅A」という名前のシード行は
    必ず既存の駅A（PK2）に、それぞれ正しく対応付けられる。例外は発生せず、データも
    入れ替わらない
    """
    _add_existing_station(
        db_session, station_id="NOID_002", name="駅B", visited=True, stay_time_min_default=88
    )
    _add_existing_station(
        db_session, station_id="NOID_001", name="駅A", visited=True, stay_time_min_default=77
    )

    rows = [
        _make_seed_station_row(station_id="NOID_001", name="駅B"),
        _make_seed_station_row(station_id="NOID_002", name="駅A"),
    ]
    result = upsert_stations(db_session, rows, {})
    db_session.commit()

    assert sorted(result.updated) == ["NOID_001", "NOID_002"]
    assert result.inserted == []
    assert result.missing_in_seed == []

    a = db_session.query(Station).filter_by(name="駅A").one()
    b = db_session.query(Station).filter_by(name="駅B").one()
    # station_idの中身は入れ替わるが、滞在時間（ユーザーデータ）は名前に正しく紐づいたまま
    assert a.station_id == "NOID_002"
    assert a.stay_time_min_default == 77
    assert b.station_id == "NOID_001"
    assert b.stay_time_min_default == 88


def test_upsert_noid_id_swap_resolves_correctly_regardless_of_row_order(db_session):
    """上記と同じ衝突しうるシナリオを、シード行の順序を逆にしても同じ結果になること
    （事前マッチングが全行一括・処理順序に依存しない設計であることの回帰テスト）
    """
    _add_existing_station(
        db_session, station_id="NOID_002", name="駅B", visited=True, stay_time_min_default=88
    )
    _add_existing_station(
        db_session, station_id="NOID_001", name="駅A", visited=True, stay_time_min_default=77
    )

    # 上のテストと行の順序を逆にしただけ
    rows = [
        _make_seed_station_row(station_id="NOID_002", name="駅A"),
        _make_seed_station_row(station_id="NOID_001", name="駅B"),
    ]
    result = upsert_stations(db_session, rows, {})
    db_session.commit()

    assert result.inserted == []
    a = db_session.query(Station).filter_by(name="駅A").one()
    b = db_session.query(Station).filter_by(name="駅B").one()
    assert a.station_id == "NOID_002"
    assert a.stay_time_min_default == 77
    assert b.station_id == "NOID_001"
    assert b.stay_time_min_default == 88


def test_upsert_gml_promotion_from_noid_is_treated_as_new_station(db_session):
    """既知の制限（レビュー4回目で明文化）: NOID_駅がシード側で正式GML IDに"昇格"する
    ケースは、識別方式そのものが変わる（name一致からID一致へ切り替わる）ため自動では
    対応付けられない。目標station_idがNOID_で始まらないため照合はstation_id一致のみで
    行われ、既存のNOID_駅は見つからない。結果として新駅としてINSERTされ、
    旧NOID_行は削除されずmissing_in_seedに残る（新IDが他の未対応駅のIDと衝突しない限り、
    例外は発生しない。データの安全な非継続）
    """
    old_hash = build_placeholder_station_id("駅A")
    _add_existing_station(
        db_session, station_id=old_hash, name="駅A", visited=True, stay_time_min_default=77
    )

    row = _make_seed_station_row(station_id="P35_900", name="駅A")
    result = upsert_stations(db_session, [row], {})
    db_session.commit()

    # 正式IDでは既存行を見つけられないため新規INSERT扱い（ユーザーデータは引き継がれない）
    assert result.inserted == ["P35_900"]
    new_row = db_session.query(Station).filter_by(station_id="P35_900").one()
    assert new_row.visited is False  # 新規行なのでデフォルト値

    # 旧NOID_行は削除されず、ユーザーデータを保持したままmissing_in_seedに残る
    assert result.missing_in_seed == [old_hash]
    old_row = db_session.query(Station).filter_by(station_id=old_hash).one()
    assert old_row.visited is True
    assert old_row.stay_time_min_default == 77


def test_upsert_raises_when_promotion_target_collides_with_untouched_station(db_session):
    """レビュー3回目で最初に発見された「昇格+ID引き継ぎ」の衝突ケース（Codexが実際に
    再現した元シナリオ）は、レビュー4回目の再設計後は_plan_station_matches内の
    「未対応の既存駅IDとの衝突チェック」で検出されるようになった。

    駅Aが正式GML ID(P35_900)に昇格する一方、駅Bのシード行は駅Aの旧ID（NOID_001）を
    新station_idとして名乗る。駅Bはname一致で正しく既存の駅Bに対応付けられるが、
    その新ID（NOID_001）は「このシードでは対応が見つからず未更新のまま残る」駅Aの
    旧行が今まさに保持しているIDと衝突する。放置するとUNIQUE制約違反になるため、
    実際の更新前にSeedMatchConflictErrorで中断する
    """
    _add_existing_station(
        db_session, station_id="NOID_002", name="駅B", visited=True, stay_time_min_default=88
    )
    _add_existing_station(
        db_session, station_id="NOID_001", name="駅A", visited=True, stay_time_min_default=77
    )

    rows = [
        _make_seed_station_row(station_id="P35_900", name="駅A"),
        _make_seed_station_row(station_id="NOID_001", name="駅B"),
    ]
    with pytest.raises(SeedMatchConflictError) as exc_info:
        upsert_stations(db_session, rows, {})

    assert "駅B" in str(exc_info.value)
    assert "NOID_001" in str(exc_info.value)

    # DBへの書き込みは一切コミットされていない
    db_session.rollback()
    a = db_session.query(Station).filter_by(name="駅A").one()
    b = db_session.query(Station).filter_by(name="駅B").one()
    assert a.station_id == "NOID_001"
    assert b.station_id == "NOID_002"
    assert b.stay_time_min_default == 88


def test_upsert_raises_on_circular_target_collision_across_three_stations(db_session):
    """3駅以上が絡む、より複雑な衝突パターン（Codexが次に狙うパターンの先回り）。

    駅Cへのシード行が存在せず（脱落想定）、駅Bのシード行のtarget station_idが
    「本来は駅C自身の仮ID」を誤って名乗ってしまっているケース。駅Aと駅Bはそれぞれ
    正しくname一致するが、駅Bの新IDが「このシードでは対応が見つからず残り続ける」
    駅Cの現IDと衝突する。3駅すべての状態を突き合わせないと検出できない衝突であり、
    単純な2駅間の取り合いチェックだけでは見逃してしまう
    """
    hash_a = build_placeholder_station_id("駅A")
    hash_b = build_placeholder_station_id("駅B")
    hash_c = build_placeholder_station_id("駅C")
    _add_existing_station(db_session, station_id=hash_a, name="駅A", stay_time_min_default=10)
    _add_existing_station(
        db_session, station_id=hash_b, name="駅B", visited=True, stay_time_min_default=20
    )
    _add_existing_station(
        db_session, station_id=hash_c, name="駅C", visited=True, stay_time_min_default=30
    )

    rows = [
        _make_seed_station_row(station_id=hash_a, name="駅A"),
        # 駅Bのtargetが自分自身のハッシュではなく、駅Cのハッシュを誤って名乗っている
        _make_seed_station_row(station_id=hash_c, name="駅B"),
        # 駅Cのシード行は存在しない（脱落）
    ]
    with pytest.raises(SeedMatchConflictError) as exc_info:
        upsert_stations(db_session, rows, {})

    assert "駅B" in str(exc_info.value)
    assert hash_c in str(exc_info.value)

    db_session.rollback()
    # 3駅すべてが例外発生前の状態のまま変化していない
    a = db_session.query(Station).filter_by(name="駅A").one()
    b = db_session.query(Station).filter_by(name="駅B").one()
    c = db_session.query(Station).filter_by(name="駅C").one()
    assert a.station_id == hash_a
    assert b.station_id == hash_b
    assert b.stay_time_min_default == 20
    assert c.station_id == hash_c
    assert c.visited is True
    assert c.stay_time_min_default == 30


def test_upsert_raises_when_duplicate_target_ids_belong_to_brand_new_stations(db_session):
    """P2指摘: シード内でtarget station_idが重複する行は、どちらも既存DBに未登録の
    新規行同士（＝既存駅との照合を試みるまでもない）であっても事前に検出して中断する。
    既存駅の照合結果に関わらず、後続のINSERTでUNIQUE制約違反になることが確定しているため
    """
    # 既存駅は無関係の1件のみ（どちらのシード行とも無関係）
    _add_existing_station(db_session, station_id="P35_999", name="無関係駅")

    rows = [
        _make_seed_station_row(station_id="P35_100", name="新駅A"),
        _make_seed_station_row(station_id="P35_100", name="新駅B"),  # station_idが重複
    ]
    with pytest.raises(SeedMatchConflictError) as exc_info:
        upsert_stations(db_session, rows, {})

    assert "P35_100" in str(exc_info.value)

    # 何も投入されていない
    db_session.rollback()
    assert db_session.query(Station).count() == 1


def test_upsert_gml_id_rotation_among_multiple_stations_resolves_without_conflict(db_session):
    """GML由来の正式ID同士（NOID_ではないケース）は、station_id一致のみで判定する
    （rule 1）。3駅を同時に更新しても、各シード行は自分のtarget station_idと一致する
    既存駅だけを一意に掴むため、原理的に衝突が起きないことを確認する（GML由来駅同士の
    通常のupsertが壊れていないことの回帰テストを兼ねる）。

    なお、rule 1はstation_idの中身だけで判定しnameは一切見ないため、station_idが
    変わらない限りIDが何行分入れ替わろうと各既存駅は自分のtarget station_idを持つ
    シード行だけに一意に対応付けられ、衝突しない（この安全性は数学的に保証される。
    衝突しうるのはNOID_行がname方式で別の識別方式の行と交差する場合のみ。詳細は
    _plan_station_matchesのdocstring参照）
    """
    _add_existing_station(
        db_session, station_id="P35_1", name="駅1", visited=True, stay_time_min_default=11
    )
    _add_existing_station(
        db_session, station_id="P35_2", name="駅2", visited=True, stay_time_min_default=22
    )
    _add_existing_station(
        db_session, station_id="P35_3", name="駅3", visited=True, stay_time_min_default=33
    )

    # station_idは変えず、名前だけ更新する3駅分のシード行を同時に処理する
    rows = [
        _make_seed_station_row(station_id="P35_1", name="更新後1"),
        _make_seed_station_row(station_id="P35_2", name="更新後2"),
        _make_seed_station_row(station_id="P35_3", name="更新後3"),
    ]
    result = upsert_stations(db_session, rows, {})
    db_session.commit()

    assert result.inserted == []
    assert sorted(result.updated) == ["P35_1", "P35_2", "P35_3"]
    # station_idが変わらないので、各駅は自分自身のデータを保持したまま名前だけ更新される
    s1 = db_session.query(Station).filter_by(station_id="P35_1").one()
    s2 = db_session.query(Station).filter_by(station_id="P35_2").one()
    s3 = db_session.query(Station).filter_by(station_id="P35_3").one()
    assert s1.name == "更新後1" and s1.stay_time_min_default == 11
    assert s2.name == "更新後2" and s2.stay_time_min_default == 22
    assert s3.name == "更新後3" and s3.stay_time_min_default == 33


def test_run_seed_rolls_back_completely_on_conflict_including_cluster_changes(db_session):
    """run_seed()が衝突を検出した場合、駅の対応関係の検証をクラスタupsertより前に行う
    ため、クラスタへの書き込みも一切発生しない（発生していても最終的にrollbackされる）。
    DBの状態が実行前後で完全に一致することを直接確認する
    """
    _add_existing_station(
        db_session, station_id="NOID_002", name="駅B", visited=True, stay_time_min_default=88
    )
    _add_existing_station(
        db_session, station_id="NOID_001", name="駅A", visited=True, stay_time_min_default=77
    )
    db_session.commit()

    def _snapshot():
        stations = [
            (s.id, s.station_id, s.name, s.visited, s.stay_time_min_default)
            for s in db_session.query(Station).order_by(Station.id).all()
        ]
        clusters = [
            (c.id, c.name, c.description)
            for c in db_session.query(Cluster).order_by(Cluster.id).all()
        ]
        return stations, clusters

    before = _snapshot()

    station_rows = [
        _make_seed_station_row(station_id="P35_900", name="駅A", cluster_name="新クラスタ1"),
        _make_seed_station_row(station_id="NOID_001", name="駅B", cluster_name="新クラスタ1"),
    ]
    cluster_rows = [{"name": "新クラスタ1", "description": None}]

    with pytest.raises(SeedMatchConflictError):
        run_seed(db_session, station_rows, cluster_rows)

    # run_seed内でrollback済みだが、念のため呼び出し側でも状態を再確認する
    db_session.rollback()
    after = _snapshot()

    assert before == after
    # 新規クラスタも一切作成されていない
    assert db_session.query(Cluster).count() == 0


def test_upsert_migrates_multiple_old_noids_regardless_of_row_order(db_session):
    """衝突しない（一意に解決可能な）ケースでは、行の順序を入れ替えても正しく処理される
    ことの回帰テスト（test_upsert_migrates_multiple_old_noids_without_unique_violationの
    行順を逆にしたもの）。事前マッチングが処理順序に依存しないことを、実際に問題なく
    upsertできる典型ケースでも確認する
    """
    _add_existing_station(db_session, station_id="NOID_001", name="無名駅A", visited=True)
    _add_existing_station(db_session, station_id="NOID_002", name="無名駅B", visited=True)

    # 行順を意図的に逆にする（無名駅B → 無名駅A の順）
    rows = [
        _make_seed_station_row(
            station_id=build_placeholder_station_id("無名駅B"), name="無名駅B"
        ),
        _make_seed_station_row(
            station_id=build_placeholder_station_id("無名駅A"), name="無名駅A"
        ),
    ]
    result = upsert_stations(db_session, rows, {})
    db_session.commit()

    assert result.inserted == []
    assert result.missing_in_seed == []
    a = db_session.query(Station).filter_by(name="無名駅A").one()
    b = db_session.query(Station).filter_by(name="無名駅B").one()
    assert a.station_id == build_placeholder_station_id("無名駅A")
    assert b.station_id == build_placeholder_station_id("無名駅B")
    assert a.visited is True
    assert b.visited is True


def test_upsert_raises_when_two_seed_rows_target_same_existing_station_id(db_session):
    """本当に曖昧で解決不能なケース: 2つのシード行が同じ既存駅のstation_idを名乗る
    （シードデータ側の重複バグ、または座標未取得駅のname重複によるハッシュ衝突等）場合は、
    どちらが正しい対応か機械的に判定できないためfail-fastする
    """
    _add_existing_station(db_session, station_id="P35_001", name="対象駅", visited=True)

    # 2つの異なるシード行が同じstation_id="P35_001"を名乗っている（データ不整合を想定）
    rows = [
        _make_seed_station_row(station_id="P35_001", name="対象駅A"),
        _make_seed_station_row(station_id="P35_001", name="対象駅B"),
    ]
    with pytest.raises(SeedMatchConflictError) as exc_info:
        upsert_stations(db_session, rows, {})

    assert "P35_001" in str(exc_info.value)


def test_upsert_raises_when_existing_db_has_duplicate_names_for_noid_row(db_session):
    """Issue #82レビュー5回目・ブロッカー3の回帰テスト。

    既存DBに同名「無名駅」が2件（station_idが異なる）ある状態で、その名前を頼りに
    照合しようとするNOID_のシード行が来た場合、単に「一致なし」として静かに新規
    INSERTしてしまうと、初回は成功しても2回目以降は新規行のstation_idが既存行の
    どちらかと衝突してUNIQUE制約違反になる（非冪等）。この曖昧さは新規INSERTを
    許す前にfail-fastで検出されるべきであることを確認する
    """
    _add_existing_station(
        db_session, station_id="NOID_001", name="無名駅", visited=True, stay_time_min_default=10
    )
    _add_existing_station(
        db_session, station_id="NOID_002", name="無名駅", visited=True, stay_time_min_default=20
    )

    row = _make_seed_station_row(station_id=build_placeholder_station_id("無名駅"), name="無名駅")
    with pytest.raises(SeedMatchConflictError) as exc_info:
        upsert_stations(db_session, [row], {})

    assert "無名駅" in str(exc_info.value)

    # 新規INSERTされておらず、DBの状態は変化していない
    db_session.rollback()
    assert db_session.query(Station).filter_by(name="無名駅").count() == 2


def test_upsert_renamed_noid_station_is_treated_as_new(db_session):
    """既知の制限: NOID_駅の改名はstation_id（name由来ハッシュ）とnameが同時に変わるため
    照合できず、新駅としてINSERTされ旧行はmissing_in_seedに載る（削除はされない）
    """
    old_hash = build_placeholder_station_id("旧名駅")
    _add_existing_station(db_session, station_id=old_hash, name="旧名駅", visited=True)

    new_hash = build_placeholder_station_id("新名駅")
    row = _make_seed_station_row(station_id=new_hash, name="新名駅")
    result = upsert_stations(db_session, [row], {})
    db_session.commit()

    assert result.inserted == [new_hash]
    assert result.missing_in_seed == [old_hash]
    # 旧行は削除されず残っている（ユーザーデータの手動移行が可能）
    old_row = db_session.query(Station).filter_by(name="旧名駅").one_or_none()
    assert old_row is not None
    assert old_row.visited is True


def test_upsert_clusters_reuses_existing_cluster_and_adds_new(db_session):
    """クラスタは既存があれば流用し、新規のみ追加する（既存クラスタは削除しない）"""
    existing = Cluster(name="大阪府1", description="ユーザーが編集したメモ")
    db_session.add(existing)
    db_session.commit()

    cluster_id_by_name = upsert_clusters(
        db_session,
        [
            {"name": "大阪府1", "description": None},
            {"name": "京都府1", "description": None},
        ],
    )
    db_session.commit()

    assert cluster_id_by_name["大阪府1"] == existing.id
    reused = db_session.get(Cluster, existing.id)
    assert reused.description == "ユーザーが編集したメモ"  # 上書きされない
    assert "京都府1" in cluster_id_by_name

    all_clusters = db_session.query(Cluster).all()
    assert len(all_clusters) == 2  # 削除されず、新規1件が追加されただけ


def test_run_seed_end_to_end_with_transform_stations(db_session):
    """transform_stationsの出力をそのままrun_seedに通しても壊れないことを確認する（結合寄りのテスト）"""
    raw_stations = [
        {
            "station_id": "P35_100",
            "name": "統合テスト駅",
            "pref": "大阪府",
            "address": "大阪市北区",
            "lat": 34.7025,
            "lon": 135.4959,
            "url": "https://example.com",
            "facilities": {"restaurant": True},
        }
    ]
    station_rows, cluster_rows = transform_stations(raw_stations)

    result = run_seed(db_session, station_rows, cluster_rows)

    assert isinstance(result, SeedUpsertResult)
    assert result.inserted == ["P35_100"]
    stored = db_session.query(Station).filter_by(station_id="P35_100").one()
    assert stored.name == "統合テスト駅"
    assert stored.good_for_lunch is True
