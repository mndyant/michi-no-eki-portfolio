// 一覧画面の表示用ヘルパー関数群。
// DESIGN.md 12章「不明点と仮置きする条件」に基づき、
// 営業時間・スタンプ受付時間が投入時の仮値のままかどうかを判定し「未確認」ラベルを出す。
import type { Station } from "./api";

// シード投入時の仮値（backend/app/services/seed_transform.py と一致させる）
const PLACEHOLDER_HOURS = "09:00-17:00";
const PLACEHOLDER_STAMP_START = "09:00";
const PLACEHOLDER_STAMP_END = "17:00";

// 曜日コード→日本語ラベル
const WEEKDAY_LABELS: Record<string, string> = {
  mon: "月",
  tue: "火",
  wed: "水",
  thu: "木",
  fri: "金",
  sat: "土",
  sun: "日",
};

/**
 * 営業時間・スタンプ受付時間が仮値のまま（実地未確認）かどうかを判定する。
 * 全曜日が仮値の営業時間 かつ スタンプ受付時間も仮値のままの場合にtrue。
 */
export function isHoursUnconfirmed(station: Station): boolean {
  const hours = Object.values(station.business_hours);
  const allPlaceholderHours =
    hours.length > 0 && hours.every((h) => h === PLACEHOLDER_HOURS);
  const placeholderStamp =
    station.stamp_start === PLACEHOLDER_STAMP_START &&
    station.stamp_end === PLACEHOLDER_STAMP_END;
  return allPlaceholderHours && placeholderStamp;
}

/** 定休日が未確認（空欄）かどうか */
export function isClosedDaysUnconfirmed(station: Station): boolean {
  return station.closed_days.trim() === "";
}

/**
 * 営業時間を短く表示する。全曜日同じ値なら「毎日 09:00-17:00」、
 * 曜日ごとに異なる場合は「月:09:00-17:00 火:...」のように列挙する。
 */
export function formatBusinessHours(hours: BusinessHoursLike): string {
  const entries = Object.entries(hours);
  if (entries.length === 0) return "不明";

  const values = entries.map(([, v]) => v);
  const allSame = values.every((v) => v === values[0]);
  if (allSame) {
    return `毎日 ${values[0]}`;
  }
  return entries
    .map(([day, range]) => `${WEEKDAY_LABELS[day] ?? day}:${range}`)
    .join(" ");
}

type BusinessHoursLike = Station["business_hours"];

/** 特徴タグの一覧（表示ラベルとフラグの対応） */
export function getFeatureTags(station: Station): string[] {
  const tags: string[] = [];
  if (station.good_for_lunch) tags.push("昼食");
  if (station.good_for_sweets) tags.push("スイーツ");
  if (station.good_for_souvenir) tags.push("土産");
  if (station.has_spa) tags.push("温泉");
  if (station.is_mountainous) tags.push("山間部");
  return tags;
}

/** 今日の日付をYYYY-MM-DD形式で返す（訪問日のデフォルト値に使用） */
export function todayIso(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
