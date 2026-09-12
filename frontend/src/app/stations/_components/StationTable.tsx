// PC(md以上)向けのテーブル型表示
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
  stations: Station[];
  clusterNameById: Map<number, string>;
  pendingVisitIds: Set<number>;
  onToggleVisit: (station: Station) => void;
  onSaveStayTime: (station: Station, minutes: number) => Promise<boolean>;
  onOpenRecords: (station: Station) => void;
}

export default function StationTable({
  stations,
  clusterNameById,
  pendingVisitIds,
  onToggleVisit,
  onSaveStayTime,
  onOpenRecords,
}: Props) {
  return (
    // 列数が多いため、狭い画面幅でも崩れないよう横スクロール可能にする
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="bg-zinc-100 text-xs uppercase text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
          <tr>
            <th className="px-3 py-2">名称</th>
            <th className="px-3 py-2">府県</th>
            <th className="px-3 py-2">訪問状態</th>
            <th className="px-3 py-2">営業時間・スタンプ受付</th>
            <th className="px-3 py-2">特徴タグ</th>
            <th className="px-3 py-2">再訪問しにくさ</th>
            <th className="px-3 py-2">クラスタ</th>
            <th className="px-3 py-2">滞在時間</th>
            <th className="px-3 py-2">外部リンク</th>
            <th className="px-3 py-2">記録</th>
          </tr>
        </thead>
        <tbody>
          {stations.map((station) => (
            <tr
              key={station.id}
              className="border-t border-zinc-100 align-top hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900/50"
            >
              <td className="px-3 py-2 font-medium">{station.name}</td>
              <td className="px-3 py-2">{station.pref}</td>
              <td className="px-3 py-2">
                <VisitToggleButton
                  visited={station.visited}
                  pending={pendingVisitIds.has(station.id)}
                  onToggle={() => onToggleVisit(station)}
                />
              </td>
              <td className="px-3 py-2">
                <HoursInfo station={station} />
              </td>
              <td className="px-3 py-2">
                <FeatureTags station={station} />
                <SpecialtyNote station={station} />
                <ReputationNote station={station} />
              </td>
              <td className="px-3 py-2">
                <RevisitScoreDetail
                  score={station.revisit_difficulty_score}
                  reason={station.revisit_difficulty_reason}
                />
              </td>
              <td className="px-3 py-2 text-zinc-600 dark:text-zinc-400">
                {station.cluster_id != null
                  ? clusterNameById.get(station.cluster_id) ?? "不明"
                  : "未設定"}
              </td>
              <td className="px-3 py-2">
                <StayTimeEditor
                  key={station.stay_time_min_default}
                  minutes={station.stay_time_min_default}
                  onSave={(minutes) => onSaveStayTime(station, minutes)}
                />
              </td>
              <td className="px-3 py-2">
                <ExternalLinks station={station} />
              </td>
              <td className="px-3 py-2">
                <button
                  type="button"
                  onClick={() => onOpenRecords(station)}
                  className="rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
                >
                  記録
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
