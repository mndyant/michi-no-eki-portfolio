from __future__ import annotations

from math import atan2, ceil, cos, degrees, radians, sin

from sqlalchemy.orm import Session

from app.models.station import Station
from app.schemas.route import (
    ManualRouteRequest,
    SuggestedPlanRead,
    SuggestRouteRequest,
    SuggestRouteResponse,
)
from app.services.ai.nl_parser import parse_free_text
from app.services.ai.reason_generator import generate_plan_reason
from app.services.distance.haversine_provider import HaversineProvider
from app.services.route.manual import HIGHWAY_DURATION_FACTOR, compute_route
from app.services.route.mountain_factor import apply_mountain_correction
from app.services.route.planner import PLAN_PROFILES, PlanStation, build_plan, to_minutes

# 探索対象の候補駅数の上限。出発地から近い順に絞り、貪欲法・2-optの計算量を抑える
MAX_CANDIDATES = 40

# 方面フィルタ: 8方位それぞれの方位角（北=0°、時計回り）。±45°の扇形でマッチさせる
DIRECTION_AZIMUTH = {
    "北": 0.0, "北東": 45.0, "東": 90.0, "南東": 135.0,
    "南": 180.0, "南西": 225.0, "西": 270.0, "北西": 315.0,
}
DIRECTION_HALF_WIDTH_DEG = 45.0

# 探索フェーズはAPIを呼ばないhaversine固定にする。
# OSRM等の外部プロバイダは最終プランの区間計算（compute_route側）でのみ使い、
# 全候補ペアへの大量リクエストを避ける（DESIGN.md 9章の制限事項）。
_search_provider = HaversineProvider()


def _travel_minutes(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    *,
    mountainous: bool = False,
) -> float:
    """2地点間の所要時間（分）。区間に山間駅が絡む場合はmountainous=Trueで係数補正する。"""
    estimate = _search_provider.get_travel(from_lat, from_lon, to_lat, to_lon)
    return apply_mountain_correction(estimate, mountainous).duration_min


def bearing_degrees(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
    """出発地から見た方位角（北=0°、時計回り0〜360°）を返す。"""
    lat1, lon1, lat2, lon2 = map(radians, (from_lat, from_lon, to_lat, to_lon))
    delta_lon = lon2 - lon1
    x = sin(delta_lon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(delta_lon)
    return (degrees(atan2(x, y)) + 360.0) % 360.0


def matches_direction(bearing: float, directions: list[str]) -> bool:
    """方位角が、選択された方面（±45°の扇形）のいずれかに入っているか。"""
    if not directions:
        return True
    for direction in directions:
        azimuth = DIRECTION_AZIMUTH[direction]
        diff = abs(bearing - azimuth)
        if min(diff, 360.0 - diff) <= DIRECTION_HALF_WIDTH_DEG:
            return True
    return False


def _load_matching_stations(db: Session, payload: SuggestRouteRequest) -> list[Station]:
    """フィルタ条件（未訪問・地域・方面）に合う駅を、絞り込み（MAX_CANDIDATES）を適用する前の全件で返す。"""
    query = db.query(Station).filter(Station.lat.isnot(None), Station.lon.isnot(None))
    if not payload.include_visited:
        query = query.filter(Station.visited.is_(False))
    if payload.prefs:
        query = query.filter(Station.pref.in_(payload.prefs))
    if payload.cluster_ids:
        query = query.filter(Station.cluster_id.in_(payload.cluster_ids))
    return [
        station
        for station in query.all()
        if matches_direction(
            bearing_degrees(payload.origin.lat, payload.origin.lon, station.lat, station.lon),
            payload.directions,
        )
    ]


def _to_plan_station(station: Station) -> PlanStation:
    return PlanStation(
        station_id=station.id,
        name=station.name,
        lat=station.lat,
        lon=station.lon,
        stamp_deadline=station.stamp_end,
        stay_min=station.stay_time_min_default,
        revisit_score=station.revisit_difficulty_score,
        food_score=(
            int(station.good_for_lunch) * 2
            + int(station.good_for_sweets)
            + int(station.good_for_souvenir)
        ),
    )


def _load_candidates(
    stations: list[Station],
    payload: SuggestRouteRequest,
    *,
    farthest_first: bool = False,
) -> list[PlanStation]:
    """マッチ済みの駅を出発地からの所要時間順に並べ、上限件数まで返す。

    既定（farthest_first=False）は近い順で、maxやgourmet等の大半のプロファイル用。
    far_first（遠方から戻る）プランは、近い順40件の中では真の遠方駅を取りこぼし
    「近場の中の最遠」しか選べなくなるため、farthest_first=Trueで遠い順に絞り込む（Issue #73）。
    """
    ordered = sorted(
        stations,
        key=lambda s: _travel_minutes(
            payload.origin.lat, payload.origin.lon, s.lat, s.lon, mountainous=s.is_mountainous
        ),
        reverse=farthest_first,
    )
    return [_to_plan_station(station) for station in ordered[:MAX_CANDIDATES]]


def _format_minutes(total_min: int) -> str:
    """0時からの分数を "HH:MM" にする（日またぎは24時間表記に折り返す）。"""
    return f"{(total_min // 60) % 24:02d}:{total_min % 60:02d}"


def _apply_free_text(payload: SuggestRouteRequest) -> SuggestRouteRequest:
    """free_textが指定されていれば、未指定（デフォルト値）のフィールドだけを解釈結果で補う。

    departure_timeは必須フィールドで常に何らかの値が入っているため対象外
    （nl_parserは抽出するが、ここでは使わない）。
    """
    if not payload.free_text:
        return payload
    parsed = parse_free_text(payload.free_text)
    updates: dict = {}
    if not payload.directions and "directions" in parsed:
        updates["directions"] = parsed["directions"]
    if payload.last_arrival_by is None and "last_arrival_by" in parsed:
        updates["last_arrival_by"] = parsed["last_arrival_by"]
    if payload.return_by is None and "return_by" in parsed:
        updates["return_by"] = parsed["return_by"]
    if not payload.use_highway and parsed.get("use_highway"):
        updates["use_highway"] = True
    if not payload.include_visited and parsed.get("include_visited"):
        updates["include_visited"] = True
    if payload.max_stations == 9 and "max_stations" in parsed:
        updates["max_stations"] = parsed["max_stations"]
    return payload.model_copy(update=updates) if updates else payload


def suggest_routes(db: Session, payload: SuggestRouteRequest) -> SuggestRouteResponse:
    """候補抽出→プロファイル別の順序構築→時刻表化の順で複数プランを作る。"""
    payload = _apply_free_text(payload)
    stations = _load_matching_stations(db, payload)
    # 各区間の山間補正判定に使う座標→is_mountainousの対応表（Issue #73）。
    # 出発地（ユーザー任意地点）はキーに存在せず、常にFalse扱いになる
    mountain_by_coord = {(station.lat, station.lon): station.is_mountainous for station in stations}
    # far_first（遠方から戻る）以外は近い順40件、far_firstは遠い順40件から選ぶ
    candidates = _load_candidates(stations, payload)
    far_candidates = _load_candidates(stations, payload, farthest_first=True)

    def base_travel_fn(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
        mountainous = mountain_by_coord.get((from_lat, from_lon), False) or mountain_by_coord.get(
            (to_lat, to_lon), False
        )
        return _travel_minutes(from_lat, from_lon, to_lat, to_lon, mountainous=mountainous)

    if payload.use_highway:
        # 高速利用時は探索・最終計算とも同じ係数で見積もる
        def travel_fn(a: float, b: float, c: float, d: float) -> float:
            return base_travel_fn(a, b, c, d) * HIGHWAY_DURATION_FACTOR
    else:
        travel_fn = base_travel_fn

    plans: list[SuggestedPlanRead] = []
    for profile in PLAN_PROFILES:
        # far_firstだけは真の遠方駅を見るため、遠い順に絞り込んだ候補集合を使う
        profile_candidates = far_candidates if profile.far_first else candidates
        candidate_plan = build_plan(
            origin_lat=payload.origin.lat,
            origin_lon=payload.origin.lon,
            departure_time=payload.departure_time,
            candidates=profile_candidates,
            travel_min_fn=travel_fn,
            profile=profile,
            max_stations=payload.max_stations,
            return_to_origin=payload.return_to_origin,
            return_by=payload.return_by,
            arrive_by=payload.last_arrival_by,
        )
        if not candidate_plan.order:
            continue
        station_ids = [station.station_id for station in candidate_plan.order]
        leg_count = len(station_ids) + (1 if payload.return_to_origin else 0)
        # 時刻表・合計・Google Maps URLは手動ルート計算をそのまま再利用する
        computation = compute_route(
            db,
            ManualRouteRequest(
                origin=payload.origin,
                departure_time=payload.departure_time,
                station_ids=station_ids,
                return_to_origin=payload.return_to_origin,
                highway_legs=list(range(leg_count)) if payload.use_highway else [],
                visit_date=payload.visit_date,
            ),
        )
        manual = computation.response
        finish_min = to_minutes(manual.stops[-1].departure)
        if computation.return_estimate is not None:
            finish_min += ceil(computation.return_estimate.duration_min)
        finish_time = _format_minutes(finish_min)
        plans.append(
            SuggestedPlanRead(
                key=profile.key,
                label=profile.label,
                description=profile.description,
                station_ids=station_ids,
                stops=manual.stops,
                totals=manual.totals,
                google_maps_url=manual.google_maps_url,
                warnings=sorted({*candidate_plan.warnings, *manual.warnings}),
                finish_time=finish_time,
                reason=generate_plan_reason(
                    profile_key=profile.key,
                    station_count=len(station_ids),
                    finish_time=finish_time,
                    requested_directions=payload.directions,
                ),
            )
        )
    warnings: list[str] = []
    if not candidates:
        warnings.append("no_candidates")
    elif not plans:
        warnings.append("no_feasible_plan")
    return SuggestRouteResponse(
        plans=plans, candidate_count=len(candidates), warnings=warnings
    )
