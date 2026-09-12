"use client";

import { useEffect, useState } from "react";
import {
  API_BASE_URL,
  ApiError,
  createVisitRecord,
  deleteVisitPhoto,
  deleteVisitRecord,
  fetchVisitRecords,
  updateStation,
  updateVisitRecord,
  uploadVisitPhoto,
  type Station,
  type VisitRecord,
  type VisitRecordPayload,
} from "@/lib/api";
import { todayIso } from "@/lib/stationDisplay";

interface VisitRecordsModalProps {
  station: Station;
  onClose: () => void;
  // 記録作成による訪問済み化や特色メモ更新を、一覧側の状態に反映させる
  onStationUpdated: (station: Station) => void;
}

// 「みかん, 梅干し」のようなカンマ区切り入力を配列に変換する
function parseItems(text: string): string[] {
  return text
    .split(/[、,]/)
    .map((item) => item.trim())
    .filter((item) => item !== "");
}

const EMPTY_FORM = {
  visitDate: "",
  purchased: "",
  food: "",
  impression: "",
  wantRevisit: "" as "" | "yes" | "no",
  nextMemo: "",
};

// 道の駅ごとの訪問記録（感想・買ってよかったもの等）と特色メモを編集するモーダル
export default function VisitRecordsModal({
  station,
  onClose,
  onStationUpdated,
}: VisitRecordsModalProps) {
  const [records, setRecords] = useState<VisitRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM, visitDate: todayIso() });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [memo, setMemo] = useState(station.user_memo ?? "");
  const [memoSaving, setMemoSaving] = useState(false);
  const [memoSaved, setMemoSaved] = useState(false);
  // 写真アップロード用: 記録ごとのタグ入力とアップロード中の記録id
  const [photoTags, setPhotoTags] = useState<Record<number, string>>({});
  const [uploadingId, setUploadingId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchVisitRecords(station.id);
        if (!cancelled) setRecords(data);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "訪問記録の取得に失敗しました");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [station.id]);

  function startEdit(record: VisitRecord) {
    setEditingId(record.id);
    setForm({
      visitDate: record.visit_date,
      purchased: record.purchased_items.join("、"),
      food: record.food.join("、"),
      impression: record.impression ?? "",
      wantRevisit: record.want_revisit === null ? "" : record.want_revisit ? "yes" : "no",
      nextMemo: record.next_memo ?? "",
    });
  }

  function resetForm() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, visitDate: todayIso() });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    const payload: VisitRecordPayload = {
      visit_date: form.visitDate,
      purchased_items: parseItems(form.purchased),
      food: parseItems(form.food),
      impression: form.impression || null,
      want_revisit: form.wantRevisit === "" ? null : form.wantRevisit === "yes",
      next_memo: form.nextMemo || null,
    };
    try {
      if (editingId !== null) {
        const updated = await updateVisitRecord(editingId, payload);
        setRecords((current) =>
          current.map((record) => (record.id === editingId ? updated : record))
        );
      } else {
        const created = await createVisitRecord(station.id, payload);
        setRecords((current) => [created, ...current]);
        // バックエンドが訪問済みに自動更新するため、一覧側にも反映する
        const visitedDate =
          station.visited_date && station.visited_date > created.visit_date
            ? station.visited_date
            : created.visit_date;
        onStationUpdated({ ...station, visited: true, visited_date: visitedDate });
      }
      resetForm();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "訪問記録の保存に失敗しました");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(recordId: number) {
    setError(null);
    try {
      await deleteVisitRecord(recordId);
      setRecords((current) => current.filter((record) => record.id !== recordId));
      if (editingId === recordId) resetForm();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "訪問記録の削除に失敗しました");
    }
  }

  async function handleUploadPhoto(recordId: number, file: File) {
    setError(null);
    setUploadingId(recordId);
    try {
      const photo = await uploadVisitPhoto(recordId, file, photoTags[recordId] ?? "");
      setRecords((current) =>
        current.map((record) =>
          record.id === recordId ? { ...record, photos: [...record.photos, photo] } : record
        )
      );
      setPhotoTags((current) => ({ ...current, [recordId]: "" }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "写真のアップロードに失敗しました");
    } finally {
      setUploadingId(null);
    }
  }

  async function handleDeletePhoto(recordId: number, photoId: number) {
    setError(null);
    try {
      await deleteVisitPhoto(photoId);
      setRecords((current) =>
        current.map((record) =>
          record.id === recordId
            ? { ...record, photos: record.photos.filter((photo) => photo.id !== photoId) }
            : record
        )
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "写真の削除に失敗しました");
    }
  }

  async function handleSaveMemo() {
    setMemoSaving(true);
    setMemoSaved(false);
    setError(null);
    try {
      const updated = await updateStation(station.id, { user_memo: memo || null });
      onStationUpdated(updated);
      setMemoSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "特色メモの保存に失敗しました");
    } finally {
      setMemoSaving(false);
    }
  }

  const inputClass =
    "rounded border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 sm:p-8"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="records-heading"
        className="w-full max-w-2xl rounded-lg bg-white p-5 shadow-xl dark:bg-zinc-950"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="records-heading" className="text-lg font-semibold">{station.name} の訪問記録</h2>
            <p className="mt-0.5 text-xs text-zinc-500">{station.pref}{station.city ? ` ${station.city}` : ""}</p>
            {/* 名産・おすすめの確認はGoogle口コミに委譲する（機械取得は規約上不可のためリンクのみ、Issue #49） */}
            <p className="mt-1 flex flex-wrap gap-3 text-xs">
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`道の駅 ${station.name}`)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 underline dark:text-blue-400"
              >
                Google Mapsで口コミ・人気商品を見る
              </a>
              {station.official_url && (
                <a
                  href={station.official_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 underline dark:text-blue-400"
                >
                  公式サイト
                </a>
              )}
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="閉じる" className="rounded border border-zinc-300 px-3 py-1 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900">
            ✕
          </button>
        </div>

        {error && (
          <div role="alert" className="mt-3 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {/* 駅の特色・自由メモ（stations.user_memo） */}
        <section className="mt-4">
          <h3 className="text-sm font-medium">特色・自由メモ</h3>
          <div className="mt-1 flex flex-col gap-2 sm:flex-row">
            <textarea
              value={memo}
              onChange={(e) => { setMemo(e.target.value); setMemoSaved(false); }}
              rows={2}
              placeholder="例: 展望台からの眺めが良い。足湯あり"
              className={`${inputClass} flex-1`}
            />
            <button type="button" onClick={handleSaveMemo} disabled={memoSaving} className="self-start rounded bg-zinc-800 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-200 dark:text-zinc-900 dark:hover:bg-zinc-300">
              {memoSaving ? "保存中…" : memoSaved ? "保存済み ✓" : "メモを保存"}
            </button>
          </div>
        </section>

        {/* 記録の追加・編集フォーム */}
        <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">{editingId !== null ? "記録を編集" : "記録を追加"}</h3>
            {editingId !== null && (
              <button type="button" onClick={resetForm} className="text-xs text-zinc-500 underline">
                編集をやめて新規追加に戻る
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">訪問日</span>
              <input required type="date" value={form.visitDate} onChange={(e) => setForm({ ...form, visitDate: e.target.value })} className={inputClass} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">また行きたい？</span>
              <select value={form.wantRevisit} onChange={(e) => setForm({ ...form, wantRevisit: e.target.value as "" | "yes" | "no" })} className={inputClass}>
                <option value="">未回答</option>
                <option value="yes">また行きたい</option>
                <option value="no">一度で十分</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">買ってよかったもの（「、」区切り）</span>
              <input type="text" value={form.purchased} onChange={(e) => setForm({ ...form, purchased: e.target.value })} placeholder="例: みかんジュース、梅干し" className={inputClass} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">食べたもの（「、」区切り）</span>
              <input type="text" value={form.food} onChange={(e) => setForm({ ...form, food: e.target.value })} placeholder="例: しらす丼" className={inputClass} />
            </label>
          </div>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-600 dark:text-zinc-400">感想</span>
            <textarea value={form.impression} onChange={(e) => setForm({ ...form, impression: e.target.value })} rows={2} placeholder="例: 海鮮が安くて新鮮。物産コーナーが広い" className={inputClass} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-600 dark:text-zinc-400">次回メモ</span>
            <input type="text" value={form.nextMemo} onChange={(e) => setForm({ ...form, nextMemo: e.target.value })} placeholder="例: 次は朝市の時間に行く" className={inputClass} />
          </label>
          <button type="submit" disabled={saving} className="self-start rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
            {saving ? "保存中…" : editingId !== null ? "更新する" : "記録を追加"}
          </button>
        </form>

        {/* 過去の記録一覧 */}
        <section className="mt-5">
          <h3 className="text-sm font-medium">これまでの記録（{records.length}件）</h3>
          {loading && <p className="mt-2 text-sm text-zinc-500">読み込み中…</p>}
          {!loading && records.length === 0 && (
            <p className="mt-2 rounded bg-zinc-50 p-4 text-center text-sm text-zinc-500 dark:bg-zinc-900">
              まだ記録がありません
            </p>
          )}
          <ul className="mt-2 flex flex-col gap-2">
            {records.map((record) => (
              <li key={record.id} className="rounded border border-zinc-200 p-3 text-sm dark:border-zinc-800">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-zinc-500">{record.visit_date}</span>
                  <span className="flex gap-2">
                    {record.want_revisit === true && (
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">また行きたい</span>
                    )}
                    <button type="button" onClick={() => startEdit(record)} className="text-xs text-blue-600 underline dark:text-blue-400">編集</button>
                    <button type="button" onClick={() => handleDelete(record.id)} className="text-xs text-red-600 underline dark:text-red-400">削除</button>
                  </span>
                </div>
                {record.impression && <p className="mt-1">{record.impression}</p>}
                {(record.purchased_items.length > 0 || record.food.length > 0) && (
                  <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
                    {record.purchased_items.length > 0 && <>購入: {record.purchased_items.join("、")}　</>}
                    {record.food.length > 0 && <>食事: {record.food.join("、")}</>}
                  </p>
                )}
                {record.next_memo && (
                  <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">次回: {record.next_memo}</p>
                )}

                {/* 写真（タグ付き）。ファイルはバックエンドの /photos で静的配信される */}
                {record.photos.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {record.photos.map((photo) => (
                      <figure key={photo.id} className="relative w-24">
                        {/* 外部ホスト(API)配信のためnext/imageではなくimgを使う */}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`${API_BASE_URL}${photo.url}`}
                          alt={photo.tags.join("、") || "訪問写真"}
                          className="h-20 w-24 rounded border border-zinc-200 object-cover dark:border-zinc-800"
                        />
                        <button
                          type="button"
                          onClick={() => handleDeletePhoto(record.id, photo.id)}
                          aria-label="写真を削除"
                          className="absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full bg-red-600 text-xs text-white hover:bg-red-700"
                        >
                          ×
                        </button>
                        {photo.tags.length > 0 && (
                          <figcaption className="mt-0.5 truncate text-[10px] text-zinc-500" title={photo.tags.join("、")}>
                            {photo.tags.join("、")}
                          </figcaption>
                        )}
                      </figure>
                    ))}
                  </div>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <input
                    type="text"
                    value={photoTags[record.id] ?? ""}
                    onChange={(e) =>
                      setPhotoTags((current) => ({ ...current, [record.id]: e.target.value }))
                    }
                    placeholder="写真のタグ（例: 名産品、外観）"
                    className="w-52 rounded border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
                  />
                  <label className="cursor-pointer rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900">
                    {uploadingId === record.id ? "アップロード中…" : "📷 写真を追加"}
                    <input
                      type="file"
                      accept="image/*"
                      className="sr-only"
                      disabled={uploadingId !== null}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadPhoto(record.id, file);
                        e.target.value = "";
                      }}
                    />
                  </label>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
