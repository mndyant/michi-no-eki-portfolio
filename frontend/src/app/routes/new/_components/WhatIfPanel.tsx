"use client";

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  calculateWhatIf,
  type ManualRouteRequest,
  type RouteStop,
  type WhatIfRouteResponse,
  type WhatIfStop,
} from "@/lib/api";

interface WhatIfPanelProps {
  // プラン計算に使った条件をそのまま土台にする
  baseRequest: ManualRouteRequest;
  // 除外トグルの表示に使う（駅名は計算結果から取る）
  baseStops: RouteStop[];
}

function warningLabel(warning: string): string {
  if (warning === "stamp_deadline_missed") return "スタンプ締切に間に合いません";
  if (warning === "tight") return "余裕15分未満";
  if (warning === "return_deadline_missed") return "帰着締切に間に合いません";
  if (warning === "waypoints_truncated") return "地図URLは先頭9駅までを含みます";
  return warning;
}

// 最遅出発の余裕を色分けバッジで表示する
function SlackBadge({ stop }: { stop: WhatIfStop }) {
  if (stop.latest_departure === null || stop.departure_slack_min === null) {
    return <span className="text-xs text-zinc-400">制約なし</span>;
  }
  const className =
    stop.departure_slack_min < 0
      ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300"
      : stop.departure_slack_min < 15
        ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
        : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300";
  return (
    <span className={`rounded px-2 py-1 text-xs font-medium ${className}`}>
      {stop.latest_departure}まで（余裕{stop.departure_slack_min}分）
    </span>
  );
}

// プラン結果に対する「もしも」を試すパネル。
// 遅延スライダー・駅除外・帰着締切を変えると、デバウンス付きで自動再計算する。
export default function WhatIfPanel({ baseRequest, baseStops }: WhatIfPanelProps) {
  const [delayMin, setDelayMin] = useState(0);
  const [excludedIds, setExcludedIds] = useState<number[]>([]);
  // 帰着締切は元プランの値（逆算モードで指定したもの）を引き継ぐ。
  // 空で初期化すると、元プランの前提だった締切が再計算から黙って外れてしまう
  const baseReturnBy = baseRequest.return_by ?? "";
  const [returnBy, setReturnBy] = useState(baseReturnBy);
  const [highwayLegs, setHighwayLegs] = useState<number[]>([]);
  const [result, setResult] = useState<WhatIfRouteResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 古いレスポンスで新しい結果を上書きしないよう、リクエストに連番を振る
  const requestSeq = useRef(0);

  const isModified =
    delayMin > 0 || excludedIds.length > 0 || returnBy !== baseReturnBy || highwayLegs.length > 0;
  const allExcluded = excludedIds.length >= baseRequest.station_ids.length;

  // 高速区間の選択肢は「除外適用後」のルートに対する区間（バックエンドの解釈と一致させる）
  const effectiveStops = baseStops.filter((stop) => !excludedIds.includes(stop.station_id));
  const legLabels: string[] = effectiveStops.map((stop, index) =>
    index === 0 ? `出発地→${stop.name}` : `${effectiveStops[index - 1].name}→${stop.name}`
  );
  if (baseRequest.return_to_origin && effectiveStops.length > 0) {
    legLabels.push(`${effectiveStops[effectiveStops.length - 1].name}→帰路`);
  }

  // 条件が変わったら400ms待ってから再計算する（スライダー操作の連打を吸収）
  useEffect(() => {
    if (!isModified || allExcluded) return;
    const seq = ++requestSeq.current;
    const timer = setTimeout(async () => {
      setPending(true);
      try {
        const response = await calculateWhatIf({
          ...baseRequest,
          delay_min: delayMin,
          excluded_station_ids: excludedIds,
          return_by: returnBy || null,
          highway_legs: highwayLegs,
        });
        if (seq === requestSeq.current) {
          setResult(response);
          setError(null);
        }
      } catch (err) {
        if (seq === requestSeq.current) {
          setError(err instanceof ApiError ? err.message : "What-if再計算に失敗しました");
        }
      } finally {
        if (seq === requestSeq.current) setPending(false);
      }
    }, 400);
    return () => {
      clearTimeout(timer);
      // リセット・全駅除外・アンマウント後の応答も無効にする。
      requestSeq.current += 1;
    };
  }, [baseRequest, delayMin, excludedIds, returnBy, highwayLegs, isModified, allExcluded]);

  function clearPreviousResult() {
    // デバウンス待機中も前の条件の結果や地図を表示しない。
    requestSeq.current += 1;
    setResult(null);
    setError(null);
    setPending(false);
  }

  function toggleExcluded(stationId: number) {
    clearPreviousResult();
    setExcludedIds((current) =>
      current.includes(stationId)
        ? current.filter((id) => id !== stationId)
        : [...current, stationId]
    );
    // 除外すると区間インデックスがずれるため、高速区間の選択はリセットする
    setHighwayLegs([]);
  }

  function toggleHighwayLeg(index: number) {
    clearPreviousResult();
    setHighwayLegs((current) =>
      current.includes(index)
        ? current.filter((leg) => leg !== index)
        : [...current, index]
    );
  }

  function reset() {
    clearPreviousResult();
    setDelayMin(0);
    setExcludedIds([]);
    setReturnBy(baseReturnBy);
    setHighwayLegs([]);
  }

  return (
    <section
      aria-labelledby="whatif-heading"
      className="flex flex-col gap-4 rounded-lg border border-violet-200 bg-violet-50/50 p-4 dark:border-violet-900 dark:bg-violet-950/30 sm:p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="whatif-heading" className="text-lg font-semibold">What-ifシミュレーション</h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            「出発が遅れたら」「この駅を飛ばしたら」を、上のプランを土台に試せます。
          </p>
        </div>
        {isModified && (
          <button type="button" onClick={reset} className="rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900">
            元のプランに戻す
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-zinc-600 dark:text-zinc-400">
            出発遅延: <span className="font-mono font-semibold">{delayMin}分</span>
          </span>
          <input
            type="range" min="0" max="180" step="5" value={delayMin}
            onChange={(e) => { clearPreviousResult(); setDelayMin(Number(e.target.value)); }}
            className="accent-violet-600"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-zinc-600 dark:text-zinc-400">帰着締切（任意）</span>
          <input
            type="time" value={returnBy} onChange={(e) => { clearPreviousResult(); setReturnBy(e.target.value); }}
            className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>
        <fieldset className="text-sm">
          <legend className="text-zinc-600 dark:text-zinc-400">飛ばす駅</legend>
          <div className="mt-1 flex flex-wrap gap-2">
            {baseStops.map((stop) => (
              <label
                key={stop.station_id}
                className={`cursor-pointer rounded-full border px-3 py-1 text-xs transition-colors ${
                  excludedIds.includes(stop.station_id)
                    ? "border-violet-600 bg-violet-600 text-white line-through"
                    : "border-zinc-300 hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
                }`}
              >
                <input
                  type="checkbox"
                  checked={excludedIds.includes(stop.station_id)}
                  onChange={() => toggleExcluded(stop.station_id)}
                  className="sr-only"
                />
                {stop.name}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      <fieldset className="text-sm">
        <legend className="text-zinc-600 dark:text-zinc-400">
          高速道路を使う区間（下道より約45%短い時間で見積り）
        </legend>
        <div className="mt-1 flex flex-wrap gap-2">
          {legLabels.map((label, index) => (
            <label
              key={`${index}-${label}`}
              className={`cursor-pointer rounded-full border px-3 py-1 text-xs transition-colors ${
                highwayLegs.includes(index)
                  ? "border-sky-600 bg-sky-600 text-white"
                  : "border-zinc-300 hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
              }`}
            >
              <input
                type="checkbox"
                checked={highwayLegs.includes(index)}
                onChange={() => toggleHighwayLeg(index)}
                className="sr-only"
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>

      {allExcluded && (
        <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          すべての駅を除外することはできません。
        </div>
      )}

      {isModified && !allExcluded && error && (
        <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {!isModified && (
        <p className="text-sm text-zinc-500">条件を変えると、ここに再計算結果が表示されます。</p>
      )}

      {isModified && !allExcluded && result && (
        <div className={`flex flex-col gap-3 ${pending ? "opacity-60" : ""}`}>
          {result.warnings.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {result.warnings.map((warning) => (
                <li key={warning} className="rounded bg-red-100 px-2 py-1 text-xs font-medium text-red-800 dark:bg-red-950 dark:text-red-300">
                  {warningLabel(warning)}
                </li>
              ))}
            </ul>
          )}
          <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-100 text-xs text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                <tr>
                  <th className="px-3 py-2">順番 / 道の駅</th>
                  <th className="px-3 py-2">到着</th>
                  <th className="px-3 py-2">出発</th>
                  <th className="px-3 py-2">締切余裕</th>
                  <th className="px-3 py-2">この時刻までに出発すれば間に合う</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {result.stops.map((stop, index) => (
                  <tr key={stop.station_id}>
                    <td className="px-3 py-2 font-medium">{index + 1}. {stop.name}</td>
                    <td className="px-3 py-2 font-mono">{stop.arrival}</td>
                    <td className="px-3 py-2 font-mono">{stop.departure}</td>
                    <td className={`px-3 py-2 ${stop.margin_min < 0 ? "font-semibold text-red-700 dark:text-red-400" : ""}`}>
                      {stop.margin_min}分
                    </td>
                    <td className="px-3 py-2"><SlackBadge stop={stop} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <a
            href={result.google_maps_url}
            target="_blank"
            rel="noopener noreferrer"
            className="self-start rounded-lg border border-violet-600 px-4 py-2 text-sm font-semibold text-violet-700 transition-colors hover:bg-violet-100 dark:text-violet-300 dark:hover:bg-violet-950"
          >
            この条件でGoogle Mapsを開く
          </a>
        </div>
      )}
    </section>
  );
}
