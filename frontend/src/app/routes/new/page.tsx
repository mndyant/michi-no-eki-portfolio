"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  calculateManualRoute,
  fetchStations,
  type ManualRouteRequest,
  type ManualRouteResponse,
  type Station,
} from "@/lib/api";
import RouteResult from "./_components/RouteResult";
import WhatIfPanel from "./_components/WhatIfPanel";

type VisitedFilter = "all" | "unvisited" | "visited";

const OSAKA_STATION = { lat: "34.7025", lon: "135.4959", label: "大阪駅" };

// 座標なしのシード駅はAPIで計算できないため、選択前に判定する。
// station_idがNOID_で始まるのはGML(国土数値情報)に未収録なだけの印であり、座標の有無とは無関係
// （Issue #74でジオコーディング補完済みの駅もNOID_のまま残る）
function hasNoCoordinates(station: Station): boolean {
  return station.lat == null || station.lon == null;
}

export default function NewRoutePage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [prefFilter, setPrefFilter] = useState("");
  const [visitedFilter, setVisitedFilter] = useState<VisitedFilter>("unvisited");
  const [nameFilter, setNameFilter] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [stayInputs, setStayInputs] = useState<Record<number, string>>({});
  const [originLat, setOriginLat] = useState(OSAKA_STATION.lat);
  const [originLon, setOriginLon] = useState(OSAKA_STATION.lon);
  const [originLabel, setOriginLabel] = useState(OSAKA_STATION.label);
  const [departureTime, setDepartureTime] = useState("08:00");
  // 訪問日（任意）。指定すると曜日別営業時間・定休日をサーバー側で評価する（Issue #71）
  const [visitDate, setVisitDate] = useState("");
  // 逆算モード: 出発時刻を入力せず「締切に間に合う最も遅い出発」をサーバーに計算させる
  const [reverseMode, setReverseMode] = useState(false);
  const [returnBy, setReturnBy] = useState("");
  const [returnToOrigin, setReturnToOrigin] = useState(false);
  // 自動並べ替え（Issue #78）: trueだとサーバー側で最適な訪問順に並べ替える。デフォルトOFFで既存動作を維持
  const [autoOrder, setAutoOrder] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [calculateError, setCalculateError] = useState<string | null>(null);
  const [result, setResult] = useState<ManualRouteResponse | null>(null);
  const [resultConditions, setResultConditions] = useState({ departureTime: "08:00", returnToOrigin: false });
  // What-ifパネルが同じ条件から再計算できるよう、成功したリクエストを保持する
  const [resultRequest, setResultRequest] = useState<ManualRouteRequest | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadStations() {
      setLoading(true);
      setLoadError(null);
      try {
        const data = await fetchStations();
        if (!controller.signal.aborted) setStations(data);
      } catch (error) {
        if (!controller.signal.aborted) {
          setLoadError(error instanceof ApiError ? error.message : "道の駅の取得に失敗しました");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    loadStations();
    return () => controller.abort();
  }, []);

  const prefs = useMemo(
    () => Array.from(new Set(stations.map((station) => station.pref))).sort((a, b) => a.localeCompare(b, "ja")),
    [stations]
  );

  const filteredStations = useMemo(
    () => stations.filter((station) => {
      if (prefFilter && station.pref !== prefFilter) return false;
      if (visitedFilter === "unvisited" && station.visited) return false;
      if (visitedFilter === "visited" && !station.visited) return false;
      return !nameFilter || station.name.includes(nameFilter.trim());
    }),
    [stations, prefFilter, visitedFilter, nameFilter]
  );

  const stationById = useMemo(
    () => new Map(stations.map((station) => [station.id, station])),
    [stations]
  );
  const selectedStations = selectedIds.flatMap((id) => {
    const station = stationById.get(id);
    return station ? [station] : [];
  });

  function toggleStation(station: Station) {
    if (hasNoCoordinates(station)) return;
    setSelectedIds((current) =>
      current.includes(station.id)
        ? current.filter((id) => id !== station.id)
        : [...current, station.id]
    );
  }

  function moveStation(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= selectedIds.length) return;
    setSelectedIds((current) => {
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function useOsakaStation() {
    setOriginLat(OSAKA_STATION.lat);
    setOriginLon(OSAKA_STATION.lon);
    setOriginLabel(OSAKA_STATION.label);
  }

  async function handleCalculate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCalculateError(null);
    const lat = Number(originLat);
    const lon = Number(originLon);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 180) {
      setCalculateError("出発地の緯度は-90〜90、経度は-180〜180の数値で入力してください。");
      return;
    }
    if (selectedIds.length === 0) {
      setCalculateError("訪問する道の駅を1駅以上選択してください。");
      return;
    }

    const stayOverrides: Record<number, number> = {};
    for (const [idText, input] of Object.entries(stayInputs)) {
      if (input === "") continue;
      const minutes = Number(input);
      if (!Number.isInteger(minutes) || minutes < 0) {
        setCalculateError("滞在時間は0以上の整数で入力してください。");
        return;
      }
      stayOverrides[Number(idText)] = minutes;
    }

    setCalculating(true);
    try {
      const request: ManualRouteRequest = {
        origin: { lat, lon, label: originLabel || null },
        departure_mode: reverseMode ? "latest" : "fixed",
        departure_time: reverseMode ? null : departureTime,
        return_by: reverseMode && returnToOrigin && returnBy ? returnBy : null,
        station_ids: selectedIds,
        stay_overrides: stayOverrides,
        return_to_origin: returnToOrigin,
        highway_legs: [],
        visit_date: visitDate || null,
        auto_order: autoOrder,
      };
      const response = await calculateManualRoute(request);
      setResult(response);
      // 逆算モードではサーバーが求めた出発時刻を以降の表示・What-ifの土台に使う
      setResultConditions({ departureTime: response.departure_time, returnToOrigin });
      setResultRequest({
        ...request,
        departure_mode: "fixed",
        departure_time: response.departure_time,
        // 自動並べ替えの結果順をそのまま固定してWhat-ifの土台にする。
        // auto_orderのまま渡すとWhat-if側で選択順に戻ってしまい、
        // 高速区間のインデックス（表示順前提）もずれるため、順序を確定させる
        station_ids: response.stops.map((stop) => stop.station_id),
        auto_order: false,
      });
    } catch (error) {
      setCalculateError(error instanceof ApiError ? error.message : "プラン計算に失敗しました");
    } finally {
      setCalculating(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-8 sm:px-6">
      <div>
        <h1 className="text-xl font-semibold sm:text-2xl">ルート作成</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          {autoOrder
            ? "選んだ道の駅をサーバー側で最適な訪問順に並べ替え、到着・出発時刻とスタンプ締切までの余裕を計算します。"
            : "道の駅を選んだ順番で、到着・出発時刻とスタンプ締切までの余裕を計算します。"}
        </p>
      </div>

      <form onSubmit={handleCalculate} className="flex flex-col gap-6">
        <section aria-labelledby="origin-heading" className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="origin-heading" className="font-semibold">1. 出発条件</h2>
            <button type="button" onClick={useOsakaStation} className="rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900">
              大阪駅をセット
            </button>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="flex flex-col gap-1 text-sm"><span className="text-zinc-600 dark:text-zinc-400">緯度</span><input required type="number" step="any" min="-90" max="90" value={originLat} onChange={(e) => { setOriginLat(e.target.value); setOriginLabel("指定地点"); }} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" /></label>
            <label className="flex flex-col gap-1 text-sm"><span className="text-zinc-600 dark:text-zinc-400">経度</span><input required type="number" step="any" min="-180" max="180" value={originLon} onChange={(e) => { setOriginLon(e.target.value); setOriginLabel("指定地点"); }} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" /></label>
            <label className="flex flex-col gap-1 text-sm"><span className="text-zinc-600 dark:text-zinc-400">出発時刻{reverseMode && "（逆算のため入力不要）"}</span><input required={!reverseMode} disabled={reverseMode} type="time" value={departureTime} onChange={(e) => setDepartureTime(e.target.value)} className="rounded border border-zinc-300 bg-white px-3 py-2 disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900" /></label>
            <label className="flex items-center gap-2 self-end rounded border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"><input type="checkbox" checked={returnToOrigin} onChange={(e) => setReturnToOrigin(e.target.checked)} className="size-4" />出発地へ戻る（往復）</label>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">訪問日（任意。指定すると曜日別の営業時間・定休日を評価）</span>
              <input type="date" value={visitDate} onChange={(e) => setVisitDate(e.target.value)} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" />
            </label>
            <label className={`flex items-center gap-2 rounded border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800 sm:col-span-2 ${autoOrder ? "cursor-not-allowed opacity-50" : ""}`}>
              <input type="checkbox" checked={reverseMode} disabled={autoOrder} onChange={(e) => setReverseMode(e.target.checked)} className="size-4" />
              出発時刻を逆算する（締切に間に合う最も遅い出発を計算）
              {autoOrder && <span className="text-xs text-zinc-500">※自動最適順とは併用できません</span>}
            </label>
            {reverseMode && returnToOrigin && (
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-zinc-600 dark:text-zinc-400">帰着締切（任意、逆算に反映）</span>
                <input type="time" value={returnBy} onChange={(e) => setReturnBy(e.target.value)} className="rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" />
              </label>
            )}
          </div>
        </section>

        <section aria-labelledby="station-heading" className="flex flex-col gap-4">
          <div>
            <h2 id="station-heading" className="font-semibold">2. 訪問する駅を選択</h2>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              {autoOrder
                ? "選んだ駅は全て、サーバー側で計算した最適な訪問順に並べ替えて表示します。"
                : "チェックした順が訪問順です。選択後に並べ替えることもできます。"}
            </p>
            <label className={`mt-3 flex items-center gap-2 rounded border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800 ${reverseMode ? "cursor-not-allowed opacity-50" : ""}`}>
              <input
                type="checkbox"
                checked={autoOrder}
                disabled={reverseMode}
                onChange={(e) => setAutoOrder(e.target.checked)}
                className="size-4"
              />
              自動で最適順にする（出発地から近い順に並べ替えて総移動時間を短縮）
              {reverseMode && <span className="text-xs text-zinc-500">※出発時刻の逆算とは併用できません</span>}
            </label>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <label className="flex flex-col gap-1 text-sm"><span className="text-zinc-500">府県</span><select value={prefFilter} onChange={(e) => setPrefFilter(e.target.value)} className="rounded border border-zinc-300 bg-white px-2 py-2 dark:border-zinc-700 dark:bg-zinc-900"><option value="">すべて</option>{prefs.map((pref) => <option key={pref} value={pref}>{pref}</option>)}</select></label>
                <label className="flex flex-col gap-1 text-sm"><span className="text-zinc-500">訪問状態</span><select value={visitedFilter} onChange={(e) => setVisitedFilter(e.target.value as VisitedFilter)} className="rounded border border-zinc-300 bg-white px-2 py-2 dark:border-zinc-700 dark:bg-zinc-900"><option value="unvisited">未訪問</option><option value="visited">訪問済み</option><option value="all">すべて</option></select></label>
                <label className="flex flex-col gap-1 text-sm"><span className="text-zinc-500">名称検索</span><input type="search" value={nameFilter} onChange={(e) => setNameFilter(e.target.value)} placeholder="例: 淡路" className="rounded border border-zinc-300 bg-white px-2 py-2 dark:border-zinc-700 dark:bg-zinc-900" /></label>
              </div>
              {loading && <p className="mt-4 text-sm text-zinc-500">道の駅を読み込み中…</p>}
              {loadError && <div className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300"><p className="font-medium">道の駅を取得できませんでした</p><p className="mt-1">{loadError}</p></div>}
              {!loading && !loadError && <div className="mt-4 max-h-96 space-y-1 overflow-y-auto pr-1">{filteredStations.length === 0 ? <p className="py-4 text-center text-sm text-zinc-500">条件に一致する駅がありません</p> : filteredStations.map((station) => { const disabled = hasNoCoordinates(station); return <label key={station.id} className={`flex items-center gap-3 rounded px-3 py-2 text-sm ${disabled ? "cursor-not-allowed bg-zinc-100 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-600" : "cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-900"}`}><input type="checkbox" checked={selectedIds.includes(station.id)} disabled={disabled} onChange={() => toggleStation(station)} className="size-4" /><span className="min-w-0 flex-1"><span className="font-medium">{station.name}</span><span className="ml-2 text-xs text-zinc-500">{station.pref}</span></span>{disabled && <span className="rounded bg-zinc-200 px-2 py-0.5 text-xs dark:bg-zinc-800">座標未取得</span>}</label>; })}</div>}
            </div>

            <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="flex items-center justify-between"><h3 className="font-medium">{autoOrder ? "選択済み（計算後に最適順で表示されます）" : "選択済み（訪問順）"}</h3><span className="text-sm text-zinc-500">{selectedStations.length}駅</span></div>
              {selectedStations.length === 0 ? <p className="mt-4 rounded bg-zinc-50 p-6 text-center text-sm text-zinc-500 dark:bg-zinc-900">左の一覧から駅を選択してください</p> : <ol className="mt-4 space-y-2">{selectedStations.map((station, index) => <li key={station.id} className="rounded border border-zinc-200 p-3 dark:border-zinc-800"><div className="flex items-start gap-2"><span className="mt-1 flex size-6 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">{index + 1}</span><div className="min-w-0 flex-1"><p className="font-medium">{station.name}</p><label className="mt-2 flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400"><span>滞在時間</span><input type="number" min="0" step="1" value={stayInputs[station.id] ?? ""} onChange={(e) => setStayInputs((current) => ({ ...current, [station.id]: e.target.value }))} placeholder={String(station.stay_time_min_default)} className="w-20 rounded border border-zinc-300 bg-white px-2 py-1 text-right text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100" /><span>分（既定 {station.stay_time_min_default}分）</span></label></div><div className="flex shrink-0 gap-1"><button type="button" disabled={autoOrder || index === 0} onClick={() => moveStation(index, -1)} aria-label={`${station.name}を上へ移動`} className="rounded border border-zinc-300 px-2 py-1 disabled:opacity-30 dark:border-zinc-700">↑</button><button type="button" disabled={autoOrder || index === selectedStations.length - 1} onClick={() => moveStation(index, 1)} aria-label={`${station.name}を下へ移動`} className="rounded border border-zinc-300 px-2 py-1 disabled:opacity-30 dark:border-zinc-700">↓</button><button type="button" onClick={() => toggleStation(station)} aria-label={`${station.name}を選択解除`} className="rounded border border-red-300 px-2 py-1 text-red-700 dark:border-red-800 dark:text-red-300">×</button></div></div></li>)}</ol>}
            </div>
          </div>
        </section>

        {calculateError && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300"><p className="font-medium">プランを計算できませんでした</p><p className="mt-1">{calculateError}</p></div>}
        <button type="submit" disabled={calculating || loading || !!loadError} className="self-start rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
          {calculating ? "プラン計算中…" : "プラン計算"}
        </button>
      </form>

      {result && <RouteResult result={result} departureTime={resultConditions.departureTime} returnToOrigin={resultConditions.returnToOrigin} stationById={stationById} />}
      {result && resultRequest && <WhatIfPanel baseRequest={resultRequest} baseStops={result.stops} />}
    </div>
  );
}
