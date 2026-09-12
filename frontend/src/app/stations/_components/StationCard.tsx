// スマホ向けのカード型表示（1駅=1カード）
"use client";

import type { Station } from "@/lib/api";
import ExternalLinks from "./ExternalLinks";
import FeatureTags from "./FeatureTags";
import HoursInfo from "./HoursInfo";
import RevisitScoreDetail from "./RevisitScoreDetail";
import SpecialtyNote from "./SpecialtyNote";
import ReputationNote from "./ReputationNote";
import StayTimeEditor from "./StayTimeEditor";
import VisitToggleButton from "./VisitToggleButton";

interface Props {
  station: Station;
  clusterName: string | null;
  visitPending: boolean;
  onToggleVisit: () => void;
  onSaveStayTime: (minutes: number) => Promise<boolean>;
  onOpenRecords: () => void;
}

export default function StationCard({
  station,
  clusterName,
  visitPending,
  onToggleVisit,
  onSaveStayTime,
  onOpenRecords,
}: Props) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold">{station.name}</h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">{station.pref}</p>
        </div>
        <VisitToggleButton
          visited={station.visited}
          pending={visitPending}
          onToggle={onToggleVisit}
        />
      </div>

      <HoursInfo station={station} />
      <FeatureTags station={station} />
      <SpecialtyNote station={station} />
      <ReputationNote station={station} />
      <ExternalLinks station={station} />

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <RevisitScoreDetail
          score={station.revisit_difficulty_score}
          reason={station.revisit_difficulty_reason}
        />
        <span className="text-zinc-500 dark:text-zinc-400">
          クラスタ: {clusterName ?? "未設定"}
        </span>
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-zinc-100 pt-2 dark:border-zinc-800">
        <span className="text-xs text-zinc-600 dark:text-zinc-400">滞在時間</span>
        <StayTimeEditor
          key={station.stay_time_min_default}
          minutes={station.stay_time_min_default}
          onSave={onSaveStayTime}
        />
      </div>

      <button
        type="button"
        onClick={onOpenRecords}
        className="self-start rounded border border-zinc-300 px-3 py-1.5 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
      >
        訪問記録・メモ
      </button>
    </div>
  );
}
