// 再訪問しにくさスコア（1-5）を表示し、算出理由をアコーディオンで開閉できるコンポーネント。
// スマホ・PC両方で同じ挙動になるよう、ツールチップではなく<details>によるアコーディオンを採用する。
"use client";

interface Props {
  score: number;
  reason: string;
}

export default function RevisitScoreDetail({ score, reason }: Props) {
  return (
    <details className="group inline-block">
      <summary
        className="inline-flex cursor-pointer list-none items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300"
        title="タップ/クリックで算出理由を表示"
      >
        再訪問しにくさ {score}/5
      </summary>
      <p className="mt-1 max-w-xs text-xs text-zinc-600 dark:text-zinc-400">
        {reason}
      </p>
    </details>
  );
}
