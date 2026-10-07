"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchStations, type Station } from "@/lib/api";

export default function DemoStations() {
  const [stations, setStations] = useState<Station[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    fetchStations().then((data) => { if (active) setStations(data); })
      .catch(() => { if (active) setError("駅データを読み込めませんでした。ページを再読み込みしてください。"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const matches = stations.filter((s) => `${s.name} ${s.address ?? ""}`.includes(query.trim()));
  return <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">OSAKA / 10 STATIONS</p><h1 className="mt-2 text-3xl font-bold">大阪の道の駅を選ぶ</h1><p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">作成者が用意した簡易JSONの実在駅。名称・住所・座標をそのまま使用しています。</p></div>
      <Link href="/routes/new" className="rounded-lg bg-emerald-800 px-5 py-3 font-semibold text-white hover:bg-emerald-700">ルート作成へ →</Link>
    </div>
    <label className="mt-8 block max-w-md text-sm font-medium">駅名・住所で検索<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="例：かなん、和泉市" className="mt-2 block w-full rounded-lg border border-zinc-300 bg-white px-4 py-3 dark:border-zinc-700 dark:bg-zinc-900" /></label>
    <p role="status" className="my-4 text-sm text-zinc-500">{loading ? "駅データを読み込み中…" : `${matches.length}駅を表示`}</p>
    {error && <p role="alert" className="text-red-700 dark:text-red-400">{error}</p>}
    {!loading && !error && matches.length === 0 && <p>該当する駅がありません。検索条件を変えてください。</p>}
    <div className="grid gap-4 sm:grid-cols-2">
      {matches.map((station, i) => <article key={station.id} className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start gap-4"><span className="rounded-full bg-emerald-50 px-3 py-2 font-mono text-sm text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">{String(i + 1).padStart(2, "0")}</span><div><h2 className="text-lg font-bold">{station.name}</h2><p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{station.address || station.pref}</p></div></div>
        <p className="mt-5 text-sm">計算上の滞在時間：{station.stay_time_min_default}分</p>
        <p className="mt-1 text-xs text-amber-800 dark:text-amber-300">営業時間・スタンプ受付は未確認（デモでは09:00〜17:00）</p>
        <div className="mt-5 flex flex-wrap gap-5 text-sm font-medium text-emerald-800 dark:text-emerald-300">
          <a href={`https://www.google.com/maps/search/?api=1&query=${station.lat},${station.lon}`} target="_blank" rel="noopener noreferrer">地図で見る ↗</a>
          {station.official_url && /^https?:\/\//.test(station.official_url) && <a href={station.official_url} target="_blank" rel="noopener noreferrer">元データの駅リンク ↗</a>}
        </div>
      </article>)}
    </div>
  </div>;
}
