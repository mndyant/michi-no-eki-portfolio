// 滞在時間（分）のインライン編集コンポーネント。
// 数値入力→保存ボタンでPUT /api/stations/{id}を呼び出し、成功/失敗を一時的に表示する。
"use client";

import { useState } from "react";

interface Props {
  minutes: number;
  onSave: (minutes: number) => Promise<boolean>;
}

// 注意: 呼び出し側は key={minutes} を付けて使うこと。
// サーバー側の値（保存成功後の反映・保存失敗時のロールバック）が変わったときに
// このコンポーネントごと再マウントさせ、入力欄の値をpropに再同期させるため
// （effect内でsetStateする代わりにReactのkeyの仕組みを使う）
export default function StayTimeEditor({ minutes, onSave }: Props) {
  // 入力中の値（サーバー値とは独立に保持し、保存が終わったら同期する）
  const [value, setValue] = useState(String(minutes));
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const isDirty = Number(value) !== minutes;

  async function handleSave() {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0 || !Number.isInteger(parsed)) {
      setFeedback("0以上の整数を入力してください");
      return;
    }
    setSaving(true);
    setFeedback(null);
    const ok = await onSave(parsed);
    setSaving(false);
    setFeedback(ok ? "保存しました" : "保存に失敗しました");
    window.setTimeout(() => setFeedback(null), 3000);
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1">
        <input
          type="number"
          min={0}
          step={5}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-16 rounded border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          aria-label="滞在時間（分）"
        />
        <span className="text-xs text-zinc-500 dark:text-zinc-400">分</span>
        {isDirty && (
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {saving ? "保存中…" : "保存"}
          </button>
        )}
      </div>
      {feedback && (
        <span
          className={
            "text-xs " +
            (feedback === "保存しました"
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-red-600 dark:text-red-400")
          }
        >
          {feedback}
        </span>
      )}
    </div>
  );
}
