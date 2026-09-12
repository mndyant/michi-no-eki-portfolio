# 推薦理由生成（ルールベース）
# 自動提案(/api/routes/suggest)の各プランに、実際の計算結果（駅数・終了時刻・方面希望との
# 一致）を反映した一言コメントを付ける。プロファイル固有の静的な説明文（SuggestedPlanRead.
# description）を補う、結果に応じた動的な一文という位置づけ。
from __future__ import annotations

# planner.PLAN_PROFILESのkeyに対応するコメントテンプレート。
# {n}=駅数, {finish}=終了時刻, {direction_note}=方面希望への言及（無ければ空文字）
_TEMPLATES = {
    "max": "{direction_note}時間の許す限り{n}駅を回り、{finish}に終了する案です",
    "light": "{direction_note}{n}駅にしぼり、締切に追われず{finish}にゆったり終了する案です",
    "gourmet": "{direction_note}グルメ・スイーツ・お土産に強い{n}駅を優先した案です",
    "rare": "{direction_note}再訪問しにくい{n}駅を今日のうちに回収する案です",
    "far_first": "{direction_note}最も遠い駅から巡り、帰りが楽になる{n}駅の案です",
}
_DEFAULT_TEMPLATE = "{direction_note}{n}駅を{finish}終了で回る案です"


def generate_plan_reason(
    *,
    profile_key: str,
    station_count: int,
    finish_time: str,
    requested_directions: list[str],
) -> str:
    """1プラン分の推薦理由（1文）を組み立てる。"""
    direction_note = ""
    if requested_directions:
        direction_note = "・".join(requested_directions) + "方面希望に沿って、"
    template = _TEMPLATES.get(profile_key, _DEFAULT_TEMPLATE)
    return template.format(direction_note=direction_note, n=station_count, finish=finish_time)
