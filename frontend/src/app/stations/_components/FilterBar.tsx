// 一覧画面のフィルタUI（府県セレクト・訪問状態セレクト・名称部分一致の検索欄）
"use client";

export type VisitedFilter = "all" | "visited" | "unvisited";

interface Props {
  prefs: string[];
  prefFilter: string;
  onPrefChange: (pref: string) => void;
  visitedFilter: VisitedFilter;
  onVisitedChange: (filter: VisitedFilter) => void;
  nameFilter: string;
  onNameChange: (name: string) => void;
}

export default function FilterBar({
  prefs,
  prefFilter,
  onPrefChange,
  visitedFilter,
  onVisitedChange,
  nameFilter,
  onNameChange,
}: Props) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 sm:flex-row sm:items-end sm:gap-4">
      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="text-zinc-600 dark:text-zinc-400">府県</span>
        <select
          value={prefFilter}
          onChange={(e) => onPrefChange(e.target.value)}
          className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">すべて</option>
          {prefs.map((pref) => (
            <option key={pref} value={pref}>
              {pref}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="text-zinc-600 dark:text-zinc-400">訪問状態</span>
        <select
          value={visitedFilter}
          onChange={(e) => onVisitedChange(e.target.value as VisitedFilter)}
          className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="all">すべて</option>
          <option value="visited">訪問済み</option>
          <option value="unvisited">未訪問</option>
        </select>
      </label>

      <label className="flex flex-[2] flex-col gap-1 text-sm">
        <span className="text-zinc-600 dark:text-zinc-400">名称で検索</span>
        <input
          type="text"
          value={nameFilter}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="例: 淡路"
          className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>
    </div>
  );
}
