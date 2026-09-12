// 道の駅一覧画面（Issue #7）
// GET /api/stations・GET /api/clusters を取得して一覧表示し、
// 府県・訪問状態・名称のフィルタ、訪問済み切替、滞在時間の編集を行う。
// 159駅程度と件数が少ないため、フィルタはクライアント側で行う（DESIGN.md 7章・12章方針）。
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  fetchClusters,
  fetchStations,
  updateStation,
  updateStationVisit,
  type Cluster,
  type Station,
} from "@/lib/api";
import { todayIso } from "@/lib/stationDisplay";
import FilterBar, { type VisitedFilter } from "./_components/FilterBar";
import StationCard from "./_components/StationCard";
import StationTable from "./_components/StationTable";
import VisitRecordsModal from "./_components/VisitRecordsModal";

export default function StationsPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // フィルタ状態
  const [prefFilter, setPrefFilter] = useState("");
  const [visitedFilter, setVisitedFilter] = useState<VisitedFilter>("all");
  const [nameFilter, setNameFilter] = useState("");

  // 訪問切替が通信中の駅id（連打防止・ボタンのローディング表示に使う）
  const [pendingVisitIds, setPendingVisitIds] = useState<Set<number>>(new Set());
  // 訪問切替が失敗した際のエラーメッセージ（駅id単位）
  const [visitErrors, setVisitErrors] = useState<Map<number, string>>(new Map());
  // 訪問記録モーダルを開いている駅（nullなら非表示）
  const [recordStation, setRecordStation] = useState<Station | null>(null);

  // 初回マウント時に一覧・クラスタを取得
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [stationList, clusterList] = await Promise.all([
          fetchStations(),
          fetchClusters(),
        ]);
        if (!cancelled) {
          setStations(stationList);
          setClusters(clusterList);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "データの取得に失敗しました");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const clusterNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const c of clusters) map.set(c.id, c.name);
    return map;
  }, [clusters]);

  // フィルタ選択肢用の府県一覧（データから動的に抽出し、五十音のブレを避けるためソート）
  const prefOptions = useMemo(() => {
    const set = new Set(stations.map((s) => s.pref));
    return Array.from(set).sort((a, b) => a.localeCompare(b, "ja"));
  }, [stations]);

  const filteredStations = useMemo(() => {
    return stations.filter((s) => {
      if (prefFilter && s.pref !== prefFilter) return false;
      if (visitedFilter === "visited" && !s.visited) return false;
      if (visitedFilter === "unvisited" && s.visited) return false;
      if (nameFilter && !s.name.includes(nameFilter)) return false;
      return true;
    });
  }, [stations, prefFilter, visitedFilter, nameFilter]);

  const visitedCountInFiltered = filteredStations.filter((s) => s.visited).length;

  // 訪問済みフラグの切替（楽観的更新。失敗時は元に戻してエラー表示）
  async function handleToggleVisit(station: Station) {
    const nextVisited = !station.visited;
    const nextDate = nextVisited ? todayIso() : null;
    const previous = station;

    setStations((prev) =>
      prev.map((s) => (s.id === station.id ? { ...s, visited: nextVisited, visited_date: nextDate } : s))
    );
    setPendingVisitIds((prev) => new Set(prev).add(station.id));
    setVisitErrors((prev) => {
      const next = new Map(prev);
      next.delete(station.id);
      return next;
    });

    try {
      const updated = await updateStationVisit(station.id, {
        visited: nextVisited,
        visited_date: nextDate,
      });
      setStations((prev) => prev.map((s) => (s.id === station.id ? updated : s)));
    } catch (e) {
      // 失敗時は元の状態に戻す
      setStations((prev) => prev.map((s) => (s.id === station.id ? previous : s)));
      setVisitErrors((prev) =>
        new Map(prev).set(
          station.id,
          e instanceof ApiError ? e.message : "訪問状態の更新に失敗しました"
        )
      );
    } finally {
      setPendingVisitIds((prev) => {
        const next = new Set(prev);
        next.delete(station.id);
        return next;
      });
    }
  }

  // 訪問記録モーダルからの更新（訪問済み化・特色メモ）を一覧へ反映する
  function handleStationUpdated(updated: Station) {
    setStations((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    setRecordStation((current) => (current?.id === updated.id ? updated : current));
  }

  // 滞在時間の保存（楽観的更新。成功/失敗をboolで返し、呼び出し元のUIで表示させる）
  async function handleSaveStayTime(station: Station, minutes: number): Promise<boolean> {
    const previous = station.stay_time_min_default;
    setStations((prev) =>
      prev.map((s) => (s.id === station.id ? { ...s, stay_time_min_default: minutes } : s))
    );
    try {
      const updated = await updateStation(station.id, { stay_time_min_default: minutes });
      setStations((prev) => prev.map((s) => (s.id === station.id ? updated : s)));
      return true;
    } catch {
      setStations((prev) =>
        prev.map((s) => (s.id === station.id ? { ...s, stay_time_min_default: previous } : s))
      );
      return false;
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-4 py-8 sm:px-6">
      <div>
        <h1 className="text-xl font-semibold sm:text-2xl">道の駅一覧</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          近畿7府県の道の駅の訪問状況・営業時間・滞在時間を確認・編集できます。
        </p>
      </div>

      <FilterBar
        prefs={prefOptions}
        prefFilter={prefFilter}
        onPrefChange={setPrefFilter}
        visitedFilter={visitedFilter}
        onVisitedChange={setVisitedFilter}
        nameFilter={nameFilter}
        onNameChange={setNameFilter}
      />

      {loading && (
        <p className="rounded-lg border border-zinc-200 bg-white p-4 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
          読み込み中…
        </p>
      )}

      {error && !loading && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          <p className="font-medium">データを取得できませんでした</p>
          <p className="mt-1">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            表示中: {filteredStations.length}件 / 全{stations.length}件
            （表示中のうち訪問済み {visitedCountInFiltered}件）
          </p>

          {Array.from(visitErrors.entries()).map(([id, message]) => (
            <p
              key={id}
              className="rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
            >
              {stations.find((s) => s.id === id)?.name ?? `駅id=${id}`}: {message}
            </p>
          ))}

          {filteredStations.length === 0 ? (
            <p className="rounded-lg border border-zinc-200 bg-white p-6 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
              条件に一致する道の駅がありません
            </p>
          ) : (
            <>
              {/* スマホ: カード型（md未満で表示） */}
              <div className="flex flex-col gap-3 md:hidden">
                {filteredStations.map((station) => (
                  <StationCard
                    key={station.id}
                    station={station}
                    clusterName={
                      station.cluster_id != null
                        ? clusterNameById.get(station.cluster_id) ?? null
                        : null
                    }
                    visitPending={pendingVisitIds.has(station.id)}
                    onToggleVisit={() => handleToggleVisit(station)}
                    onSaveStayTime={(minutes) => handleSaveStayTime(station, minutes)}
                    onOpenRecords={() => setRecordStation(station)}
                  />
                ))}
              </div>

              {/* PC: テーブル型（md以上で表示） */}
              <div className="hidden md:block">
                <StationTable
                  stations={filteredStations}
                  clusterNameById={clusterNameById}
                  pendingVisitIds={pendingVisitIds}
                  onToggleVisit={handleToggleVisit}
                  onSaveStayTime={handleSaveStayTime}
                  onOpenRecords={setRecordStation}
                />
              </div>
            </>
          )}
        </>
      )}

      {recordStation && (
        <VisitRecordsModal
          station={recordStation}
          onClose={() => setRecordStation(null)}
          onStationUpdated={handleStationUpdated}
        />
      )}
    </div>
  );
}
