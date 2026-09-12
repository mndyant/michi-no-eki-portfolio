import type { Station } from "@/lib/api";

export default function ReputationNote({ station }: { station: Station }) {
  const items = station.reputation_items as string[];
  if (!items || items.length === 0) return null;

  return (
    <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-0.5">
      <span className="font-medium text-amber-600 dark:text-amber-400">👍 口コミ人気: </span>
      {items.join(" / ")}
    </p>
  );
}
