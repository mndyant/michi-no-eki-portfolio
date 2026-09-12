"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  fetchStations,
  suggestRoutes,
  type Station,
  type SuggestRouteResponse,
} from "@/lib/api";
import PlanCard from "./_components/PlanCard";

const OSAKA_STATION = { lat: "34.7025", lon: "135.4959", label: "大阪駅" };

// 方面フィルタの8方位（バックエンドのDIRECTION_KEYSと一致させる）
const DIRECTIONS = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"] as const;

// 自動ルート提案ページ（フェーズ3）。
// 出発条件を入力すると、評価の重みを変えた複数プラン（効率重視・安全重視・
// グルメ重視・再訪困難優先）を並べて比較できる。
export default function SuggestRoutePage() {
  // 府県フィルタの選択肢を出すために駅一覧を読み込む
  const [stations, setStations] = useState<Station[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [originLat, setOriginLat] = useState(OSAKA_STATION.lat);
  const [originLon, setOriginLon] = useState(OSAKA_STATION.lon);
  const [originLabel, setOriginLabel] = useState(OSAKA_STATION.label);
  const [departureTime, setDepartureTime] = useState("08:00");
  // 訪問日（任意）。指定すると曜日別営業時間・定休日をサーバー側で評価する（Issue #71）
  const [visitDate, setVisitDate] = useState("");
  const [maxStations, setMaxStations] = useState("9");
  const [selectedPrefs, setSelectedPrefs] = useState<string[]>([]);
  const [selectedDirections, setSelectedDirections] = useState<string[]>([]);
  const [includeVisited, setIncludeVisited] = useState(false);
  const [returnToOrigin, setReturnToOrigin] = useState(false);
  const [returnBy, setReturnBy] = useState("");
  const [lastArrivalBy, setLastArrivalBy] = useState("");
  const [useHighway, setUseHighway] = useState(false);
  const [freeText, setFreeText] = useState("");

  const [suggesting, setSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [result, setResult] = useState<SuggestRouteResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadStations() {
      try {
        const data = await fetchStations();
        if (!controller.signal.aborted) setStations(data);
      } catch (error) {
        if (!controller.signal.aborted) {
          setLoadError(error instanceof ApiError ? error.message : "道の駅の取得に失敗しました");
        }
      }
    }
    loadStations();
    return () => controller.abort();
  }, []);

  const prefs = useMemo(
    () => Array.from(new Set(stations.map((station) => station.pref))).sort((a, b) => a.localeCompare(b, "ja")),
    [stations]
  );

  // 提案結果の駅ごとに「営業時間未確認」バッジを表示するための参照用マップ
  const stationById = useMemo(
    () => new Map(stations.map((station) => [station.id, station])),
    [stations]
  );

  function togglePref(pref: string) {
    setSelectedPrefs((current) =>
      current.includes(pref) ? current.filter((item) => item !== pref) : [...current, pref]
    );
  }

  function toggleDirection(direction: string) {
    setSelectedDirections((current) =>
      current.includes(direction)
        ? current.filter((item) => item !== direction)
        : [...current, direction]
    );
  }

  function useOsakaStation() {
    setOriginLat(OSAKA_STATION.lat);
    setOriginLon(OSAKA_STATION.lon);
    setOriginLabel(OSAKA_STATION.label);
  }

  async function handleSuggest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuggestError(null);
    const lat = Number(originLat);
    const lon = Number(originLon);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 180) {
      setSuggestError("出発地の緯度は-90〜90、経度は-180〜180の数値で入力してください。");
      return;
    }

    setSuggesting(true);
    try {
      const response = await suggestRoutes({
        origin: { lat, lon, label: originLabel || null },
        departure_time: departureTime,
        max_stations: Number(maxStations),
        prefs: selectedPrefs,
        cluster_ids: [],
        include_visited: includeVisited,
        return_to_origin: returnToOrigin,
        return_by: returnBy || null,
        last_arrival_by: lastArrivalBy || null,
        directions: selectedDirections,
        use_highway: useHighway,
        free_text: freeText.trim() || null,
        visit_date: visitDate || null,
      });
      setResult(response);
    } catch (error) {
      setSuggestError(error instanceof ApiError ? error.message : "プラン提案に失敗しました");
    } finally {
      setSuggesting(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-8 px-4 py-8 sm:px-6">
      <div>
        <h1 className="text-xl font-semibold sm:text-2xl">自動ルート提案</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          時間・地域・方面を決めると、未訪問の駅を回る複数プラン（最大効率・軽めなど）を自動で組み立てて比較できます。
        </p>
      </div>

      <form onSubmit={handleSuggest} className="flex flex-col gap-6">
        <section aria-labelledby="condition-heading" className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="condition-heading" className="font-semibold">出発条件</h2>
            <button type="button" onClick={useOsakaStation} className="rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900">
              大阪駅をセット
            </button>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">緯度</span>
              <input required type="number" step="any" min="-90" max="90" value={originLat} onChange={(e) => { setOriginLat(e.target.value); setOriginLabel("指定地点"); }} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">経度</span>
              <input required type="number" step="any" min="-180" max="180" value={originLon} onChange={(e) => { setOriginLon(e.target.value); setOriginLabel("指定地点"); }} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">出発時刻</span>
              <input required type="time" value={departureTime} onChange={(e) => setDepartureTime(e.target.value)} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">上限駅数（通常は9のまま）</span>
              <input required type="number" min="1" max="9" step="1" value={maxStations} onChange={(e) => setMaxStations(e.target.value)} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">訪問日（任意。指定すると曜日別の営業時間・定休日を評価）</span>
              <input type="date" value={visitDate} onChange={(e) => setVisitDate(e.target.value)} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" />
            </label>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">最後の駅に到着したい時刻（任意）</span>
              <input type="time" value={lastArrivalBy} onChange={(e) => setLastArrivalBy(e.target.value)} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">帰着締切（任意）</span>
              <input type="time" value={returnBy} onChange={(e) => setReturnBy(e.target.value)} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" />
            </label>
            <label className="flex items-center gap-2 rounded border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
              <input type="checkbox" checked={returnToOrigin} onChange={(e) => setReturnToOrigin(e.target.checked)} className="size-4" />
              出発地へ戻る（往復）
            </label>
            <label className="flex items-center gap-2 rounded border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
              <input type="checkbox" checked={useHighway} onChange={(e) => setUseHighway(e.target.checked)} className="size-4" />
              高速道路も使う
            </label>
          </div>
          <label className="mt-4 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={includeVisited} onChange={(e) => setIncludeVisited(e.target.checked)} className="size-4" />
            訪問済みの駅も候補に含める
          </label>
          <label className="mt-4 flex flex-col gap-1 text-sm">
            <span className="text-zinc-600 dark:text-zinc-400">
              自然文で希望を伝える（任意。下の方面・時刻を未指定のときだけ解釈結果で補います）
            </span>
            <textarea
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              placeholder="例: 南方面を回って16:30までに最終駅に着きたい"
              rows={2}
              className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
          <fieldset className="mt-4">
            <legend className="text-sm text-zinc-600 dark:text-zinc-400">方面（未選択なら全方位。「なんとなくこっち方面」で絞れます）</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {DIRECTIONS.map((direction) => (
                <label
                  key={direction}
                  className={`cursor-pointer rounded-full border px-3 py-1.5 text-sm transition-colors ${
                    selectedDirections.includes(direction)
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-zinc-300 hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
                  }`}
                >
                  <input type="checkbox" checked={selectedDirections.includes(direction)} onChange={() => toggleDirection(direction)} className="sr-only" />
                  {direction}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="mt-4">
            <legend className="text-sm text-zinc-600 dark:text-zinc-400">対象の府県（未選択なら全域）</legend>
            {loadError && <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">府県一覧を取得できませんでした（全域を対象に提案します）: {loadError}</p>}
            <div className="mt-2 flex flex-wrap gap-2">
              {prefs.map((pref) => (
                <label
                  key={pref}
                  className={`cursor-pointer rounded-full border px-3 py-1.5 text-sm transition-colors ${
                    selectedPrefs.includes(pref)
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-zinc-300 hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
                  }`}
                >
                  <input type="checkbox" checked={selectedPrefs.includes(pref)} onChange={() => togglePref(pref)} className="sr-only" />
                  {pref}
                </label>
              ))}
            </div>
          </fieldset>
        </section>

        {suggestError && (
          <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
            <p className="font-medium">プランを提案できませんでした</p>
            <p className="mt-1">{suggestError}</p>
          </div>
        )}
        <button type="submit" disabled={suggesting} className="self-start rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
          {suggesting ? "プラン提案中…" : "プランを提案"}
        </button>
      </form>

      {result && (
        <section aria-labelledby="plans-heading" className="flex flex-col gap-4">
          <div>
            <h2 id="plans-heading" className="text-xl font-semibold">提案プラン</h2>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              候補{result.candidate_count}駅から生成しました。条件を変えて再提案できます。
            </p>
          </div>

          {result.warnings.includes("no_candidates") && (
            <p className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
              条件に合う候補駅がありません。府県や訪問済みの条件を見直してください。
            </p>
          )}
          {result.warnings.includes("no_feasible_plan") && (
            <p className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
              締切・帰着条件を満たすプランを作れませんでした。出発時刻を早めるか、帰着締切を緩めてください。
            </p>
          )}

          {/* プランは5案（最大効率・軽め・グルメ・再訪困難・遠方から戻る）のため3列で折り返す */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {result.plans.map((plan) => (
              <PlanCard key={plan.key} plan={plan} stationById={stationById} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
