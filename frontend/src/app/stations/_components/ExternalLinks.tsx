// 公式サイトとGoogleマップ口コミへの外部リンクをまとめて表示する小さなコンポーネント（Issue #79）。
// 公式サイト: station.official_url がある駅のみ表示（無い駅は非表示、フォールバックしない）。
// Googleマップ口コミ: place_idを持たないため検索リンクで代替。全駅で常に表示する。
import type { Station } from "@/lib/api";

export default function ExternalLinks({ station }: { station: Station }) {
  const mapsQuery = encodeURIComponent(`${station.name} ${station.pref}`);
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${mapsQuery}`;

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {station.official_url && (
        <a
          href={station.official_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded border border-zinc-300 px-2 py-0.5 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
        >
          🔗 公式サイト
        </a>
      )}
      <a
        href={mapsUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 rounded border border-zinc-300 px-2 py-0.5 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
      >
        📍 口コミ
      </a>
    </div>
  );
}
