// 特徴タグ（昼食/スイーツ/土産/温泉/山間部）を並べて表示する小さなコンポーネント
import { getFeatureTags } from "@/lib/stationDisplay";
import type { Station } from "@/lib/api";

export default function FeatureTags({ station }: { station: Station }) {
  const tags = getFeatureTags(station);
  if (tags.length === 0) {
    return <span className="text-xs text-zinc-400 dark:text-zinc-600">特徴タグなし</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span
          key={tag}
          className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-800 dark:bg-sky-950 dark:text-sky-300"
        >
          {tag}
        </span>
      ))}
    </div>
  );
}
