// バックエンドAPIとの通信をまとめたモジュール。
// 型定義は backend/app/schemas/station.py, cluster.py, route.py のPydanticスキーマと一致させている。
// コンポーネント側はこのモジュール経由でのみAPIを呼び出す（fetch呼び出しをここに閉じ込める）。

// APIのベースURL。.env.local の NEXT_PUBLIC_API_BASE_URL を使い、未設定時はローカル開発用の既定値を使う
// （写真の静的配信URL組み立てに使うためexportする）
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// 曜日ごとの営業時間。例: {"mon": "09:00-17:00", ...}（backend: business_hoursカラム）
export type BusinessHours = Record<string, string>;

// GET /api/stations・GET /api/stations/{id} のレスポンス型（schemas/station.py StationRead相当）
export interface Station {
  id: number;
  station_id: string;
  name: string;
  pref: string;
  city: string | null;
  address: string | null;
  lat: number | null;
  lon: number | null;
  official_url: string | null;
  business_hours: BusinessHours;
  stamp_start: string;
  stamp_end: string;
  closed_days: string;
  visited: boolean;
  visited_date: string | null;
  stay_time_min_default: number;
  facility_scale: string;
  good_for_lunch: boolean;
  good_for_sweets: boolean;
  good_for_souvenir: boolean;
  has_spa: boolean;
  scenery_score: number | null;
  is_mountainous: boolean;
  revisit_difficulty_score: number;
  revisit_difficulty_reason: string;
  cluster_id: number | null;
  reputation_items: unknown[];
  local_specialty: unknown[];
  seasonal_specialty: unknown[];
  user_memo: string | null;
  source: string;
  last_verified_at: string;
}

// GET /api/clusters のレスポンス型（schemas/cluster.py ClusterRead相当）
export interface Cluster {
  id: number;
  name: string;
  description: string | null;
}

// PATCH /api/stations/{id}/visit の送信body（schemas/station.py StationVisitUpdate相当）
export interface StationVisitPayload {
  visited: boolean;
  visited_date: string | null;
}

// POST /api/routes/manual の送信body（schemas/route.py ManualRouteRequest相当）
export interface ManualRouteRequest {
  origin: {
    lat: number;
    lon: number;
    label: string | null;
  };
  // fixed: departure_timeから順方向に計算 / latest: 締切から最遅出発を逆算
  departure_mode: "fixed" | "latest";
  // fixedモードでは必須、latestモードではnull可（サーバーが逆算する）
  departure_time: string | null;
  // 帰着締切。latestモードの逆算制約として使う
  return_by: string | null;
  station_ids: number[];
  stay_overrides: Record<number, number>;
  return_to_origin: boolean;
  // 高速道路を使う区間のインデックス（0=出発地→1駅目、i=i駅目→i+1駅目、駅数=帰路）
  highway_legs: number[];
  // 訪問日（YYYY-MM-DD、任意）。指定時のみ曜日別営業時間・定休日を評価する（Issue #71）
  visit_date: string | null;
  // trueの場合、station_idsの並び順ではなくサーバー側で最適な訪問順に並べ替える（Issue #78）
  auto_order: boolean;
}

// POST /api/routes/manual の各立ち寄り駅（schemas/route.py RouteStopRead相当）
export interface RouteStop {
  station_id: number;
  name: string;
  arrival: string;
  departure: string;
  stay_min: number;
  stamp_deadline: string;
  margin_min: number;
  warnings: string[];
}

// POST /api/routes/manual の集計値（schemas/route.py RouteTotals相当）
export interface RouteTotals {
  travel_min: number;
  distance_km: number;
  stay_min: number;
}

// POST /api/routes/manual のレスポンス（schemas/route.py ManualRouteResponse相当）
export interface ManualRouteResponse {
  stops: RouteStop[];
  totals: RouteTotals;
  google_maps_url: string;
  warnings: string[];
  // 実際に計算へ使った出発時刻（逆算モードではサーバーが求めた最遅出発時刻）
  departure_time: string;
}

// POST /api/routes/what-if の送信body（schemas/route.py WhatIfRouteRequest相当）
// 手動ルートの条件に「遅延・駅除外・帰着締切」の変化分を加えて再計算する
export interface WhatIfRouteRequest extends ManualRouteRequest {
  delay_min: number;
  excluded_station_ids: number[];
  return_by: string | null;
}

// What-if結果の立ち寄り駅（schemas/route.py WhatIfStopRead相当）
export interface WhatIfStop extends RouteStop {
  // この時刻までに出発すれば以降の締切に間に合う。制約がなければnull
  latest_departure: string | null;
  // 最遅出発時刻 - 実際の出発時刻。負なら以降のどこかで間に合わない
  departure_slack_min: number | null;
}

// POST /api/routes/what-if のレスポンス（schemas/route.py WhatIfRouteResponse相当）
export interface WhatIfRouteResponse {
  stops: WhatIfStop[];
  totals: RouteTotals;
  google_maps_url: string;
  warnings: string[];
  applied_delay_min: number;
  excluded_station_ids: number[];
}

// POST /api/routes/suggest の送信body（schemas/route.py SuggestRouteRequest相当）
export interface SuggestRouteRequest {
  origin: {
    lat: number;
    lon: number;
    label: string | null;
  };
  departure_time: string;
  max_stations: number;
  prefs: string[];
  cluster_ids: number[];
  include_visited: boolean;
  return_to_origin: boolean;
  return_by: string | null;
  // 最後の駅への到着締切（例: "17:30"）
  last_arrival_by: string | null;
  // 出発地から見た方面（8方位: 北/北東/東/南東/南/南西/西/北西）
  directions: string[];
  // 全区間で高速道路を使う想定で見積もる
  use_highway: boolean;
  // 自然文でのルート希望（任意、フェーズ5）。指定済みの他フィールドは上書きしない
  free_text: string | null;
  // 訪問日（YYYY-MM-DD、任意）。指定時のみ曜日別営業時間・定休日を評価する（Issue #71）
  visit_date: string | null;
}

// 自動提案された1プラン（schemas/route.py SuggestedPlanRead相当）
export interface SuggestedPlan {
  key: string;
  label: string;
  description: string;
  station_ids: number[];
  stops: RouteStop[];
  totals: RouteTotals;
  google_maps_url: string;
  warnings: string[];
  // 行程の終了時刻。帰着ありなら帰着時刻、なしなら最終駅の出発時刻
  finish_time: string;
  // 実際の計算結果を反映した一言コメント（フェーズ5）
  reason: string;
}

// POST /api/routes/suggest のレスポンス（schemas/route.py SuggestRouteResponse相当）
export interface SuggestRouteResponse {
  plans: SuggestedPlan[];
  candidate_count: number;
  warnings: string[];
}

// 訪問記録の写真（schemas/visit_photo.py VisitPhotoRead相当）
export interface VisitPhoto {
  id: number;
  visit_record_id: number;
  url: string; // 例: /photos/12_abc.jpg（表示時は API_BASE_URL と結合する）
  tags: string[];
}

// 訪問記録（schemas/visit_record.py VisitRecordRead相当）
export interface VisitRecord {
  id: number;
  station_id: number;
  visit_date: string;
  purchased_items: string[];
  food: string[];
  impression: string | null;
  photo_url: string | null;
  want_revisit: boolean | null;
  next_memo: string | null;
  photos: VisitPhoto[];
}

// 訪問記録の作成・更新body（schemas/visit_record.py VisitRecordCreate/Update相当）
export interface VisitRecordPayload {
  visit_date: string;
  purchased_items: string[];
  food: string[];
  impression: string | null;
  want_revisit: boolean | null;
  next_memo: string | null;
}

// PUT /api/stations/{id} の送信body。渡した項目だけ部分更新される（schemas/station.py StationUpdate相当）
export type StationUpdatePayload = Partial<
  Omit<
    Station,
    "id" | "visited" | "visited_date" | "reputation_items" | "local_specialty" | "seasonal_specialty"
  >
>;

// API呼び出し失敗時にthrowするエラー。
// バックエンド未起動などのネットワークエラーと、APIが返したエラーレスポンスの両方をこの型で表現する
export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// FastAPIのdetailは文字列または検証エラー配列。配列をErrorへ直接渡すと
// "[object Object]"になるため、対象フィールドと説明を取り出す。
function errorDetailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item: unknown) => {
      if (!item || typeof item !== "object" || !("msg" in item) || typeof item.msg !== "string") return [];
      const location = "loc" in item && Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
      return [location ? `${location}: ${item.msg}` : item.msg];
    });
    if (messages.length) return `入力内容を確認してください。${messages.join(" / ")}`;
  }
  return fallback;
}

// fetchの共通ラッパー。エラーを日本語メッセージに変換して投げる
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch {
    // fetch自体が失敗＝ネットワークエラー（バックエンド未起動など）
    throw new ApiError(
      `APIサーバー（${API_BASE_URL}）に接続できません。バックエンドが起動しているか確認してください。`
    );
  }

  if (!res.ok) {
    let detail = `APIエラーが発生しました（status: ${res.status}）`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail = errorDetailMessage(body?.detail, detail);
    } catch {
      // レスポンスがJSONでない場合はデフォルトメッセージを使う
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) {
    // DELETE等でボディが無いレスポンス
    return undefined as T;
  }
  return (await res.json()) as T;
}

// 道の駅一覧を取得する。フィルタはクライアント側で行うため引数なしで全件取得する
export function fetchStations(): Promise<Station[]> {
  return apiFetch<Station[]>("/api/stations");
}

// クラスタ一覧を取得する（クラスタ名表示用）
export function fetchClusters(): Promise<Cluster[]> {
  return apiFetch<Cluster[]>("/api/clusters");
}

// 訪問済みフラグ・訪問日を更新する
export function updateStationVisit(
  id: number,
  payload: StationVisitPayload
): Promise<Station> {
  return apiFetch<Station>(`/api/stations/${id}/visit`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// 道の駅の情報を部分更新する（滞在時間の編集などに使用）
export function updateStation(
  id: number,
  payload: StationUpdatePayload
): Promise<Station> {
  return apiFetch<Station>(`/api/stations/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

// 遅延・駅除外・帰着締切を適用して再計算し、各駅の最遅出発時刻を取得する
export function calculateWhatIf(
  payload: WhatIfRouteRequest
): Promise<WhatIfRouteResponse> {
  return apiFetch<WhatIfRouteResponse>("/api/routes/what-if", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// 条件に合う駅から、評価の重みを変えた複数プランを自動生成する
export function suggestRoutes(
  payload: SuggestRouteRequest
): Promise<SuggestRouteResponse> {
  return apiFetch<SuggestRouteResponse>("/api/routes/suggest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// 指定した道の駅の訪問記録一覧を新しい順で取得する
export function fetchVisitRecords(stationId: number): Promise<VisitRecord[]> {
  return apiFetch<VisitRecord[]>(`/api/stations/${stationId}/visit-records`);
}

// 訪問記録を作成する（駅は自動で訪問済みになる）
export function createVisitRecord(
  stationId: number,
  payload: VisitRecordPayload
): Promise<VisitRecord> {
  return apiFetch<VisitRecord>(`/api/stations/${stationId}/visit-records`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// 訪問記録を更新する
export function updateVisitRecord(
  recordId: number,
  payload: VisitRecordPayload
): Promise<VisitRecord> {
  return apiFetch<VisitRecord>(`/api/visit-records/${recordId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

// 訪問記録を削除する
export function deleteVisitRecord(recordId: number): Promise<void> {
  return apiFetch<void>(`/api/visit-records/${recordId}`, { method: "DELETE" });
}

// 訪問記録に写真をアップロードする（multipartのためapiFetchを使わない）
export async function uploadVisitPhoto(
  recordId: number,
  file: File,
  tags: string
): Promise<VisitPhoto> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("tags", tags);
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/visit-records/${recordId}/photos`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new ApiError(
      `APIサーバー（${API_BASE_URL}）に接続できません。バックエンドが起動しているか確認してください。`
    );
  }
  if (!res.ok) {
    let detail = `写真のアップロードに失敗しました（status: ${res.status}）`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail = errorDetailMessage(body?.detail, detail);
    } catch {
      // JSONでない場合はデフォルトメッセージのまま
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as VisitPhoto;
}

// 写真を削除する
export function deleteVisitPhoto(photoId: number): Promise<void> {
  return apiFetch<void>(`/api/photos/${photoId}`, { method: "DELETE" });
}

// 選択順をそのまま訪問順として、手動ルートの時刻表と地図URLを計算する
export function calculateManualRoute(
  payload: ManualRouteRequest
): Promise<ManualRouteResponse> {
  return apiFetch<ManualRouteResponse>("/api/routes/manual", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
