// 名産・特徴（station.local_specialty）を表示する小さなコンポーネント。
// フェーズ5（Issue #51）でWikipedia抜粋からルールベース抽出した文をそのまま出す。
// 抽出できた駅は少数（159駅中3駅程度）なので、無い場合は何も表示しない。
import type { Station } from "@/lib/api";

export default function SpecialtyNote({ station }: { station: Station }) {
  const items = station.local_specialty as string[];
  if (!items || items.length === 0) return null;
  return (
    <p className="text-xs text-zinc-600 dark:text-zinc-400">
      <span className="font-medium text-zinc-700 dark:text-zinc-300">名産: </span>
      {items.join(" / ")}
    </p>
  );
}
