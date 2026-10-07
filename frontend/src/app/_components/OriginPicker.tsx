"use client";

import { useId } from "react";
import { ORIGIN_AREAS, type Origin } from "@/lib/origins";

const GROUPS = [...new Set(ORIGIN_AREAS.map((area) => area.group))];

export default function OriginPicker({ value, onChange, disabled = false }: {
  value: Origin;
  onChange: (origin: Origin) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const selected = ORIGIN_AREAS.find((area) => area.lat === value.lat && area.lon === value.lon);

  return <div className="mt-4 space-y-3">
    <label htmlFor={id} className="block text-sm font-medium">大体の出発エリア（車）</label>
    <p id={`${id}-help`} className="text-sm leading-6 text-zinc-600 dark:text-zinc-400">
      今いる場所や車を出す場所に近いエリアを選んでください。現在地の取得・位置情報の許可は不要です。
    </p>
    <select id={id} value={selected?.id ?? ""} disabled={disabled} aria-describedby={`${id}-help`}
      onChange={(event) => {
        const area = ORIGIN_AREAS.find((item) => item.id === event.target.value);
        if (area) onChange({ lat: area.lat, lon: area.lon, label: area.label });
      }}
      className="min-h-11 w-full max-w-xl rounded-lg border border-zinc-300 bg-white px-3 py-3 text-base disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900">
      {GROUPS.map((group) => <optgroup key={group} label={group}>
        {ORIGIN_AREAS.filter((area) => area.group === group).map((area) => <option key={area.id} value={area.id}>{area.label}</option>)}
      </optgroup>)}
    </select>
    <div className="rounded-lg bg-zinc-50 px-4 py-3 text-sm dark:bg-zinc-900">
      <p className="font-medium" aria-live="polite">出発地：{value.label}</p>
      <p className="mt-1 leading-6 text-zinc-600 dark:text-zinc-400">選んだエリアの代表地点から、車で巡る所要時間を概算します。正確な駐車位置や道路・渋滞は反映しません。</p>
      <a href={`https://www.google.com/maps/search/?api=1&query=${value.lat},${value.lon}`} target="_blank" rel="noopener noreferrer"
        className="mt-1 inline-flex min-h-11 items-center text-blue-700 underline dark:text-blue-300">地図で代表地点を確認</a>
    </div>
  </div>;
}
