from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Callable, Sequence

# 訪問順の自動提案ロジック（DESIGN.md 8章）。
# DBやAPIに依存しない純粋関数のみで構成し、pytestで固定ケースを検証できるようにする。

# 締切までの余裕がこの分数を下回ると「急ぎ」とみなし、優先度を上げ始める窓
URGENCY_WINDOW_MIN = 120


@dataclass(frozen=True, slots=True)
class PlanStation:
    """自動提案の計算に必要な道の駅情報だけを持つ。"""

    station_id: int
    name: str
    lat: float
    lon: float
    stamp_deadline: str  # "HH:MM"
    stay_min: int
    revisit_score: int  # 再訪問しにくさ 1-5
    food_score: int  # グルメ・買い物適性 0-4（lunch×2 + sweets + souvenir）


@dataclass(frozen=True, slots=True)
class PlanProfile:
    """評価関数の重みセット。プロファイルを変えることで複数プランを作る。"""

    key: str
    label: str
    description: str
    w_travel: float  # 移動時間ペナルティの重み
    w_deadline: float  # 締切が近い駅を先に回す重み（EDF要素）
    w_revisit: float  # 再訪問しにくさスコアの重み
    w_food: float  # グルメ・買い物適性の重み
    min_margin_min: int  # 到着時に締切へ最低限確保したい余裕（分）
    max_stations_cap: int | None = None  # プロファイル固有の駅数上限（Noneなら依頼値のまま）
    # 遠方先行モード: 最初に最も遠い駅を選び、以降は出発地へ近づく駅を優先する。
    # 並びの意図（遠→近）を保つため2-optの反転改善は行わない
    far_first: bool = False


# 5プラン分のプロファイル（DESIGN.md 8章-6・13-2章）。
# 駅数は入力でなく結果:「最大効率」は時間の許す限り回り、「軽め」は少なめ＋余裕重視。
# 先頭がUIで最初に表示されるデフォルト。ユーザー要望（Issue #47）により「遠方から戻る」を先頭にする
PLAN_PROFILES: tuple[PlanProfile, ...] = (
    PlanProfile(
        key="far_first",
        label="遠方から戻る",
        description="最も遠い駅を最初に訪ね、出発地の方へ戻りながら回る案（帰りが楽）",
        w_travel=0.6, w_deadline=1.0, w_revisit=0.0, w_food=0.0, min_margin_min=10,
        far_first=True,
    ),
    PlanProfile(
        key="max",
        label="最大効率",
        description="時間内に未訪問の駅をできるだけ多く回る案",
        # EDF（締切優先）が基本戦略のため、効率重視でも締切緊急度の重みは落とさない
        w_travel=1.0, w_deadline=1.0, w_revisit=0.0, w_food=0.0, min_margin_min=10,
    ),
    PlanProfile(
        key="light",
        label="軽め",
        description="最大4駅・締切余裕30分以上でゆったり回る案",
        w_travel=1.0, w_deadline=1.5, w_revisit=0.0, w_food=0.0,
        min_margin_min=30, max_stations_cap=4,
    ),
    PlanProfile(
        key="gourmet",
        label="グルメ重視",
        description="食事・スイーツ・土産に強い駅を優先して組み込む案",
        w_travel=0.6, w_deadline=1.0, w_revisit=0.0, w_food=1.0, min_margin_min=10,
    ),
    PlanProfile(
        key="rare",
        label="再訪困難優先",
        description="再訪問しにくい駅を今日のうちに回収することを優先する案",
        w_travel=0.4, w_deadline=1.0, w_revisit=1.0, w_food=0.0, min_margin_min=10,
    ),
)

# 遠方先行モードで「出発地に近づく駅」に与える加点の重み。
# 近づいた分数（現在地の帰り時間 - 候補の帰り時間）×この係数を採点に足す。
# w_travelより小さくすること: 大きいと途中の駅を飛ばして一気に戻る並びになり、
# 逆に0だと出発地から遠ざかる寄り道を防げない
HOMEWARD_WEIGHT = 0.4

# 2地点間の所要時間（分）を返す関数。純粋関数に保つため呼び出し側から注入する
TravelMinutesFn = Callable[[float, float, float, float], float]


def to_minutes(hhmm: str) -> int:
    """"HH:MM" を0時からの分数に変換する。"""
    parsed = datetime.strptime(hhmm, "%H:%M")
    return parsed.hour * 60 + parsed.minute


@dataclass(frozen=True, slots=True)
class SimulationResult:
    feasible: bool
    total_travel_min: int
    finish_min: int  # 最終駅出発（帰着ありなら帰着）時刻


def simulate_order(
    origin_lat: float,
    origin_lon: float,
    departure_min: int,
    order: Sequence[PlanStation],
    travel_min_fn: TravelMinutesFn,
    min_margin_min: int,
    return_to_origin: bool,
    return_by_min: int | None,
    arrive_by_min: int | None = None,
) -> SimulationResult:
    """訪問順を時刻シミュレーションし、制約充足と総移動時間を返す。"""
    current_lat, current_lon = origin_lat, origin_lon
    now = departure_min
    total_travel = 0
    for station in order:
        travel = ceil(travel_min_fn(current_lat, current_lon, station.lat, station.lon))
        arrival = now + travel
        if to_minutes(station.stamp_deadline) - arrival < min_margin_min:
            return SimulationResult(False, 0, 0)
        # 「最後の駅にHH:MMまでに到着」制約: 全駅の到着がこれ以前である必要がある
        if arrive_by_min is not None and arrival > arrive_by_min:
            return SimulationResult(False, 0, 0)
        total_travel += travel
        now = arrival + station.stay_min
        current_lat, current_lon = station.lat, station.lon
    if return_to_origin and order:
        back = ceil(travel_min_fn(current_lat, current_lon, origin_lat, origin_lon))
        total_travel += back
        now += back
    if return_by_min is not None and now > return_by_min:
        return SimulationResult(False, 0, 0)
    return SimulationResult(True, total_travel, now)


def _score_candidate(
    profile: PlanProfile,
    travel_min: int,
    margin_min: int,
    station: PlanStation,
) -> float:
    """貪欲法の1ステップで候補駅を採点する。大きいほど優先。"""
    # 締切が近い（余裕が窓より小さい）ほど1に近づく緊急度。EDFの距離コスト加味版
    urgency = max(0, URGENCY_WINDOW_MIN - margin_min) / URGENCY_WINDOW_MIN
    return (
        -profile.w_travel * travel_min
        + profile.w_deadline * urgency * 60
        + profile.w_revisit * station.revisit_score * 10
        + profile.w_food * station.food_score * 15
    )


def _greedy_order(
    origin_lat: float,
    origin_lon: float,
    departure_min: int,
    candidates: Sequence[PlanStation],
    travel_min_fn: TravelMinutesFn,
    profile: PlanProfile,
    max_stations: int,
    return_to_origin: bool,
    return_by_min: int | None,
    arrive_by_min: int | None,
) -> list[PlanStation]:
    """実行可能な候補から採点最大の駅を1つずつ選ぶ貪欲法。"""
    selected: list[PlanStation] = []
    remaining = list(candidates)
    current_lat, current_lon = origin_lat, origin_lon
    now = departure_min
    while remaining and len(selected) < max_stations:
        best: PlanStation | None = None
        best_score = float("-inf")
        best_arrival = 0
        # 遠方先行モードの2駅目以降で使う「現在地から出発地への帰り時間」
        current_home = (
            travel_min_fn(current_lat, current_lon, origin_lat, origin_lon)
            if profile.far_first and selected
            else 0.0
        )
        for station in remaining:
            travel = ceil(travel_min_fn(current_lat, current_lon, station.lat, station.lon))
            arrival = now + travel
            margin = to_minutes(station.stamp_deadline) - arrival
            if margin < profile.min_margin_min:
                continue
            if arrive_by_min is not None and arrival > arrive_by_min:
                continue
            # 帰着締切があるなら「この駅に寄っても戻れるか」まで見て選ぶ
            if return_by_min is not None:
                finish = arrival + station.stay_min
                if return_to_origin:
                    finish += ceil(
                        travel_min_fn(station.lat, station.lon, origin_lat, origin_lon)
                    )
                if finish > return_by_min:
                    continue
            score = _score_candidate(profile, travel, margin, station)
            if profile.far_first:
                if not selected:
                    # 最初の1駅は遠さを最優先: 移動ペナルティを打ち消し、遠い駅ほど高得点にする
                    score += 2 * profile.w_travel * travel
                else:
                    # 出発地に近づく駅ほど加点し、遠→近の戻り順を作る
                    candidate_home = travel_min_fn(
                        station.lat, station.lon, origin_lat, origin_lon
                    )
                    score += HOMEWARD_WEIGHT * (current_home - candidate_home)
            if score > best_score:
                best, best_score, best_arrival = station, score, arrival
        if best is None:
            break
        selected.append(best)
        remaining.remove(best)
        now = best_arrival + best.stay_min
        current_lat, current_lon = best.lat, best.lon
    return selected


def _two_opt_improve(
    origin_lat: float,
    origin_lon: float,
    departure_min: int,
    order: list[PlanStation],
    travel_min_fn: TravelMinutesFn,
    profile: PlanProfile,
    return_to_origin: bool,
    return_by_min: int | None,
    arrive_by_min: int | None,
) -> list[PlanStation]:
    """2-opt: 部分区間の反転で総移動時間が減り、かつ制約を満たす場合だけ採用する。"""
    if len(order) < 3:
        return order
    best_order = order
    best_travel = simulate_order(
        origin_lat, origin_lon, departure_min, best_order, travel_min_fn,
        profile.min_margin_min, return_to_origin, return_by_min, arrive_by_min,
    ).total_travel_min
    improved = True
    while improved:
        improved = False
        for i in range(len(best_order) - 1):
            for j in range(i + 1, len(best_order)):
                trial = best_order[:i] + best_order[i : j + 1][::-1] + best_order[j + 1 :]
                result = simulate_order(
                    origin_lat, origin_lon, departure_min, trial, travel_min_fn,
                    profile.min_margin_min, return_to_origin, return_by_min, arrive_by_min,
                )
                if result.feasible and result.total_travel_min < best_travel:
                    best_order, best_travel = trial, result.total_travel_min
                    improved = True
        # 改善が続く限り繰り返す（駅数は最大9なので計算量は小さい）
    return best_order


@dataclass(frozen=True, slots=True)
class PlanCandidate:
    """1プロファイル分の提案結果（順序のみ。時刻表化は呼び出し側で行う）。"""

    profile: PlanProfile
    order: tuple[PlanStation, ...]
    warnings: tuple[str, ...]


def build_plan(
    origin_lat: float,
    origin_lon: float,
    departure_time: str,
    candidates: Sequence[PlanStation],
    travel_min_fn: TravelMinutesFn,
    profile: PlanProfile,
    max_stations: int,
    return_to_origin: bool = False,
    return_by: str | None = None,
    arrive_by: str | None = None,
) -> PlanCandidate:
    """1プロファイル分の訪問順を貪欲法+2-optで構築する。"""
    departure_min = to_minutes(departure_time)
    return_by_min = to_minutes(return_by) if return_by is not None else None
    arrive_by_min = to_minutes(arrive_by) if arrive_by is not None else None
    # プロファイル固有の駅数上限（軽め=4駅など）を依頼値と合わせて適用する
    if profile.max_stations_cap is not None:
        max_stations = min(max_stations, profile.max_stations_cap)
    order = _greedy_order(
        origin_lat, origin_lon, departure_min, candidates, travel_min_fn,
        profile, max_stations, return_to_origin, return_by_min, arrive_by_min,
    )
    if not profile.far_first:
        # 遠方先行モードでは遠→近の並びが崩れるため2-optを適用しない
        order = _two_opt_improve(
            origin_lat, origin_lon, departure_min, order, travel_min_fn,
            profile, return_to_origin, return_by_min, arrive_by_min,
        )
    warnings: list[str] = []
    if not order:
        warnings.append("no_feasible_station")
    elif len(order) < min(max_stations, len(candidates)):
        # 制約により希望件数まで組み込めなかった（DESIGN.md 8章-7の件数削減に相当）
        warnings.append("fewer_stations_than_requested")
    return PlanCandidate(profile=profile, order=tuple(order), warnings=tuple(warnings))
