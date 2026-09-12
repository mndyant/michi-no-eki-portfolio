// 訪問済み/未訪問バッジ兼切替ボタン。
// クリックでPATCH /api/stations/{id}/visit を呼ぶ（実際の通信は呼び出し元のonToggleに委譲する）。
"use client";

interface Props {
  visited: boolean;
  pending: boolean;
  onToggle: () => void;
}

export default function VisitToggleButton({ visited, pending, onToggle }: Props) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={pending}
      className={
        "rounded-full px-3 py-1 text-xs font-medium transition-colors disabled:cursor-wait disabled:opacity-60 " +
        (visited
          ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:hover:bg-emerald-900"
          : "bg-zinc-200 text-zinc-700 hover:bg-zinc-300 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700")
      }
    >
      {pending ? "更新中…" : visited ? "訪問済み" : "未訪問"}
    </button>
  );
}
