// 営業時間・スタンプ受付時間・定休日の表示。
// 仮値のままの項目にはDESIGN.md 12章の方針に従い「未確認」ラベルを付ける。
import { formatBusinessHours, isClosedDaysUnconfirmed, isHoursUnconfirmed } from "@/lib/stationDisplay";
import type { Station } from "@/lib/api";

function UnconfirmedBadge() {
  return (
    <span className="rounded bg-zinc-200 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
      未確認
    </span>
  );
}

export default function HoursInfo({ station }: { station: Station }) {
  const unconfirmed = isHoursUnconfirmed(station);

  return (
    <div className="flex flex-col gap-0.5 text-xs text-zinc-700 dark:text-zinc-300">
      <div className="flex items-center gap-1">
        <span>営業: {formatBusinessHours(station.business_hours)}</span>
        {unconfirmed && <UnconfirmedBadge />}
      </div>
      <div className="flex items-center gap-1">
        <span>
          スタンプ受付: {station.stamp_start}〜{station.stamp_end}
        </span>
        {unconfirmed && <UnconfirmedBadge />}
      </div>
      <div className="flex items-center gap-1">
        <span>定休日: {station.closed_days || "不明"}</span>
        {isClosedDaysUnconfirmed(station) && <UnconfirmedBadge />}
      </div>
    </div>
  );
}
