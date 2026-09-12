import type { ManualRouteResponse, RouteStop, Station } from "@/lib/api";
import { isClosedDaysUnconfirmed, isHoursUnconfirmed } from "@/lib/stationDisplay";

interface RouteResultProps {
  result: ManualRouteResponse;
  departureTime: string;
  returnToOrigin: boolean;
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

// APIには帰着時刻専用フィールドがないため、出発時刻と合計所要時間から算出する
function calculateReturnTime(
  departureTime: string,
  result: ManualRouteResponse
): string {
  const [hours, minutes] = departureTime.split(":").map(Number);
  const totalMinutes = hours * 60 + minutes + result.totals.travel_min + result.totals.stay_min;
  const dayOffset = Math.floor(totalMinutes / (24 * 60));
  const timeInDay = totalMinutes % (24 * 60);
  const time = `${String(Math.floor(timeInDay / 60)).padStart(2, "0")}:${String(
    timeInDay % 60
  ).padStart(2, "0")}`;
  return dayOffset > 0 ? `翌日+${dayOffset - 1}日 ${time}` : time;
}

function warningLabel(warning: string): string {
  if (warning === "stamp_deadline_missed") return "スタンプ締切に間に合いません";
  if (warning === "tight") return "余裕15分未満";
  if (warning === "wait_for_open") return "営業開始前到着（開店まで待機）";
  if (warning === "closed_day") return "訪問日が定休日の可能性";
  return warning;
}

// 一覧画面と同じロジックで「営業時間未確認（仮値のまま）」を判定して表示する
function UnconfirmedHoursBadge({ station }: { station: Station | undefined }) {
  if (!station) return null;
  if (!isHoursUnconfirmed(station) && !isClosedDaysUnconfirmed(station)) return null;
  return (
    <span className="rounded bg-zinc-200 px-2 py-1 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
      営業時間未確認
    </span>
  );
}

function WarningBadges({ stop }: { stop: RouteStop }) {
  if (stop.warnings.length === 0) {
    return <span className="text-xs text-emerald-700 dark:text-emerald-400">問題なし</span>;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {stop.warnings.map((warning) => (
        <span
          key={warning}
          className={
            warning === "stamp_deadline_missed"
              ? "rounded bg-red-100 px-2 py-1 text-xs font-medium text-red-800 dark:bg-red-950 dark:text-red-300"
              : "rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300"
          }
        >
          {warningLabel(warning)}
        </span>
      ))}
    </div>
  );
}

export default function RouteResult({
  result,
  departureTime,
  returnToOrigin,
  stationById,
}: RouteResultProps) {
  return (
    <section aria-labelledby="route-result-heading" className="flex flex-col gap-4">
      <div>
        <h2 id="route-result-heading" className="text-xl font-semibold">
          プラン結果
        </h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          条件を編集して「プラン計算」を押すと、同じ場所で再計算できます。
        </p>
      </div>

      {result.warnings.includes("waypoints_truncated") && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          Google Mapsの経由地上限を超えたため、地図URLには先頭9駅までを含めています。タイムテーブルは選択した全駅分です。
        </div>
      )}

      {result.warnings.includes("no_feasible_departure") && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          0時に出発しても全ての締切に間に合わない組み合わせです。駅を減らすか順番を見直してください（以下は0:00出発として計算）。
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950/40">
          <p className="text-xs text-zinc-500">出発時刻</p>
          <p className="mt-1 font-mono text-lg font-semibold">{result.departure_time}</p>
        </div>
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950/40">
          <p className="text-xs text-zinc-500">最終駅到着</p>
          <p className="mt-1 font-mono text-lg font-semibold">
            {result.stops[result.stops.length - 1]?.arrival ?? "—"}
          </p>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-xs text-zinc-500">総移動時間</p>
          <p className="mt-1 font-mono text-lg font-semibold">{formatMinutes(result.totals.travel_min)}</p>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-xs text-zinc-500">総距離</p>
          <p className="mt-1 font-mono text-lg font-semibold">{result.totals.distance_km.toFixed(1)} km</p>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-xs text-zinc-500">総滞在時間</p>
          <p className="mt-1 font-mono text-lg font-semibold">{formatMinutes(result.totals.stay_min)}</p>
        </div>
        {returnToOrigin && (
          <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <p className="text-xs text-zinc-500">帰着時刻</p>
            <p className="mt-1 font-mono text-lg font-semibold">
              {calculateReturnTime(departureTime, result)}
            </p>
          </div>
        )}
      </div>

      {/* スマホでは1駅ずつカード表示する */}
      <div className="flex flex-col gap-3 md:hidden">
        {result.stops.map((stop, index) => (
          <article
            key={stop.station_id}
            className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs text-zinc-500">{index + 1}番目</p>
                <h3 className="font-semibold">{stop.name}</h3>
              </div>
              <div className="flex flex-col items-end gap-1">
                <WarningBadges stop={stop} />
                <UnconfirmedHoursBadge station={stationById.get(stop.station_id)} />
              </div>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <div><dt className="text-xs text-zinc-500">到着</dt><dd className="font-mono">{stop.arrival}</dd></div>
              <div><dt className="text-xs text-zinc-500">出発</dt><dd className="font-mono">{stop.departure}</dd></div>
              <div><dt className="text-xs text-zinc-500">滞在</dt><dd>{stop.stay_min}分</dd></div>
              <div><dt className="text-xs text-zinc-500">スタンプ締切</dt><dd className="font-mono">{stop.stamp_deadline}</dd></div>
              <div className="col-span-2"><dt className="text-xs text-zinc-500">締切までの余裕</dt><dd>{stop.margin_min}分</dd></div>
            </dl>
          </article>
        ))}
      </div>

      {/* md以上では時刻を比較しやすいテーブル表示にする */}
      <div className="hidden overflow-x-auto rounded-lg border border-zinc-200 bg-white md:block dark:border-zinc-800 dark:bg-zinc-950">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-100 text-xs text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
            <tr>
              <th className="px-3 py-3">順番 / 道の駅</th><th className="px-3 py-3">到着</th>
              <th className="px-3 py-3">滞在</th><th className="px-3 py-3">出発</th>
              <th className="px-3 py-3">締切</th><th className="px-3 py-3">余裕</th>
              <th className="px-3 py-3">警告</th><th className="px-3 py-3">営業時間</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {result.stops.map((stop, index) => (
              <tr key={stop.station_id}>
                <td className="px-3 py-3 font-medium">{index + 1}. {stop.name}</td>
                <td className="px-3 py-3 font-mono">{stop.arrival}</td>
                <td className="px-3 py-3">{stop.stay_min}分</td>
                <td className="px-3 py-3 font-mono">{stop.departure}</td>
                <td className="px-3 py-3 font-mono">{stop.stamp_deadline}</td>
                <td className="px-3 py-3">{stop.margin_min}分</td>
                <td className="px-3 py-3"><WarningBadges stop={stop} /></td>
                <td className="px-3 py-3"><UnconfirmedHoursBadge station={stationById.get(stop.station_id)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <a
        href={result.google_maps_url}
        target="_blank"
        rel="noopener noreferrer"
        className="self-start rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        Google Mapsで開く
      </a>
    </section>
  );
}
