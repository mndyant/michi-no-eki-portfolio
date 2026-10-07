import type { ManualRouteRequest } from "./api";

export type Origin = ManualRouteRequest["origin"];

// Area representatives, not station entrances or exact parking locations.
// Source and retrieval date: docs/origin-areas.md.
export const ORIGIN_AREAS = [
  { id: "umeda", group: "大阪市内", label: "梅田・大阪駅周辺", lat: 34.7025, lon: 135.4959 },
  { id: "namba", group: "大阪市内", label: "なんば・難波周辺", lat: 34.667603, lon: 135.501724 },
  { id: "abeno", group: "大阪市内", label: "天王寺・阿倍野周辺", lat: 34.645733, lon: 135.513321 },
  { id: "takatsuki", group: "北摂・北河内", label: "高槻・桃園町周辺", lat: 34.845566, lon: 135.616089 },
  { id: "hirakata", group: "北摂・北河内", label: "枚方・大垣内町周辺", lat: 34.812756, lon: 135.650024 },
  { id: "higashiosaka", group: "東大阪・中河内", label: "東大阪・荒本周辺", lat: 34.680332, lon: 135.598755 },
  { id: "yao", group: "東大阪・中河内", label: "八尾・本町周辺", lat: 34.627277, lon: 135.600861 },
  { id: "sakai", group: "堺・泉州・南河内", label: "堺・南瓦町周辺", lat: 34.573936, lon: 135.481506 },
  { id: "kishiwada", group: "堺・泉州・南河内", label: "岸和田・岸城町周辺", lat: 34.458885, lon: 135.37114 },
  { id: "izumisano", group: "堺・泉州・南河内", label: "泉佐野・市場東周辺", lat: 34.405407, lon: 135.328125 },
  { id: "kawachinagano", group: "堺・泉州・南河内", label: "河内長野・原町周辺", lat: 34.460682, lon: 135.574127 },
] as const;

export const DEFAULT_ORIGIN: Origin = {
  lat: ORIGIN_AREAS[0].lat,
  lon: ORIGIN_AREAS[0].lon,
  label: ORIGIN_AREAS[0].label,
};
