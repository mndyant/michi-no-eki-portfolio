import type { RouteStop, Station, SuggestedPlan } from "@/lib/api";
import { isClosedDaysUnconfirmed, isHoursUnconfirmed } from "@/lib/stationDisplay";

interface PlanCardProps {
  plan: SuggestedPlan;
  // 駅ごとの「営業時間未確認」バッジ表示に使う（一覧画面の未確認判定ロジックを再利用）
  stationById: Map<number, Station>;
}

// 分数を「2時間15分」のような読みやすい表記に変換する
function formatMinutes(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest}分`;
  return rest === 0 ? `${hours}時間` : `${hours}時間${rest}分`;
}

// プラン・駅の警告コードを日本語ラベルに変換する
function warningLabel(warning: string): string {
  if (warning === "stamp_deadline_missed") return "スタンプ締切に間に合いません";
  if (warning === "tight") return "余裕15分未満";
  if (warning === "fewer_stations_than_requested")
    return "制約により希望駅数まで組み込めませんでした";
  if (warning === "waypoints_truncated")
    return "地図URLは先頭9駅までを含みます";
  if (warning === "wait_for_open") return "営業開始前到着（開店まで待機）";
  if (warning === "closed_day") return "訪問日が定休日の可能性";
  return warning;
}

// 一覧画面と同じロジックで「営業時間未確認（仮値のまま）」を判定して表示する
function UnconfirmedHoursBadge({ station }: { station: Station | undefined }) {
  if (!station) return null;
  if (!isHoursUnconfirmed(station) && !isClosedDaysUnconfirmed(station)) return null;
  return (
    <span className="rounded bg-zinc-200 px-1.5 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
      営業時間未確認
    </span>
  );
}

function StopWarnings({ stop }: { stop: RouteStop }) {
  if (stop.warnings.length === 0) return null;
  return (
    <span className="flex flex-wrap gap-1">
      {stop.warnings.map((warning) => (
        <span
          key={warning}
          className={
            warning === "stamp_deadline_missed"
              ? "rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-800 dark:bg-red-950 dark:text-red-300"
              : "rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300"
          }
        >
          {warningLabel(warning)}
        </span>
      ))}
    </span>
  );
}

// 自動提案された1プランを、比較しやすいカード形式で表示する
export default function PlanCard({ plan, stationById }: PlanCardProps) {
  return (
    <article className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 sm:p-5">
      <header>
        <h3 className="text-lg font-semibold">{plan.label}</h3>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{plan.description}</p>
        <p className="mt-2 rounded bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:bg-blue-950 dark:text-blue-200">
          {plan.reason}
        </p>
      </header>

      {plan.warnings.length > 0 && (
        <ul className="flex flex-col gap-1">
          {plan.warnings.map((warning) => (
            <li
              key={warning}
              className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
            >
              {warningLabel(warning)}
            </li>
          ))}
        </ul>
      )}

      <dl className="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
        <div className="rounded bg-zinc-50 p-2 dark:bg-zinc-900">
          <dt className="text-xs text-zinc-500">訪問駅数</dt>
          <dd className="mt-0.5 font-mono font-semibold">{plan.stops.length}駅</dd>
        </div>
        <div className="rounded bg-zinc-50 p-2 dark:bg-zinc-900">
          <dt className="text-xs text-zinc-500">終了時刻</dt>
          <dd className="mt-0.5 font-mono font-semibold">{plan.finish_time}</dd>
        </div>
        <div className="rounded bg-zinc-50 p-2 dark:bg-zinc-900">
          <dt className="text-xs text-zinc-500">総移動</dt>
          <dd className="mt-0.5 font-mono font-semibold">{formatMinutes(plan.totals.travel_min)}</dd>
        </div>
        <div className="rounded bg-zinc-50 p-2 dark:bg-zinc-900">
          <dt className="text-xs text-zinc-500">総滞在</dt>
          <dd className="mt-0.5 font-mono font-semibold">{formatMinutes(plan.totals.stay_min)}</dd>
        </div>
      </dl>

      <ol className="flex flex-col gap-2">
        {plan.stops.map((stop, index) => (
          <li
            key={stop.station_id}
            className="rounded border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
          >
            <div className="flex items-center gap-2">
              <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 truncate font-medium">{stop.name}</span>
              <span className="shrink-0 font-mono text-xs text-zinc-500">
                {stop.arrival}〜{stop.departure}
              </span>
            </div>
            <div className="mt-1 flex items-center justify-between gap-2 pl-7 text-xs text-zinc-500">
              <span>締切 {stop.stamp_deadline}（余裕 {stop.margin_min}分）</span>
              <span className="flex flex-wrap items-center justify-end gap-1">
                <StopWarnings stop={stop} />
                <UnconfirmedHoursBadge station={stationById.get(stop.station_id)} />
              </span>
            </div>
          </li>
        ))}
      </ol>

      <a
        href={plan.google_maps_url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-auto self-start rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        Google Mapsで開く
      </a>
    </article>
  );
}
