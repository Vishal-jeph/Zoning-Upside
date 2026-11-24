// Site data produced by pipeline/potential.py (web/public/data/sites.geojson) and the client-side filters.
import type { ApprovedZone } from "@/lib/rules";

export type SiteStatus = "scored" | "condo_building" | "rules_not_loaded";

export interface Flag { code: string; text: string }

export interface SiteProps {
  site_id: string;
  block: string;
  lot: string;
  merged_lots: string[] | null;
  location: string | null;
  prop_class: string | null;
  zone: string | null;
  zone_key: string | null;
  district_name: string | null;
  bldg_desc: string | null;
  lot_desc: string | null;
  year_built: number | null;
  sale_date: string | null;
  sale_price: number | null;
  land_value: number | null;
  impr_value: number | null;
  net_value: number | null;
  lot_area_basis: string | null;
  lot_width_ft: number | null;
  lot_depth_ft: number | null;
  is_condo_building: boolean;
  condo_unit_count: number | null;
  commercial_units: number | null;
  is_vacant_land: boolean;
  in_historic_district: boolean;
  in_flood_hazard_area: boolean;
  in_redev_area: boolean;
  has_redev_agreement: boolean;
  in_zoning_in_progress: boolean;
  redev_area_url: string | null;
  redev_agreement_url: string | null;
  ordinance_url: string | null;
  guide_url: string | null;
  // potential
  status: SiteStatus;
  rule_district: string | null;
  existing_stories: number | null;
  existing_units: number | null;
  existing_units_basis: string | null;
  lot_area: number | null;
  allowed_stories: number | null;
  stories_formula: string | null;
  stories_note: string | null;
  allowed_units: number | null;
  units_formula: string | null;
  units_note: string | null;
  residential_permitted: string | null;
  unused_stories: number | null;
  unused_units: number | null;
  nonconforming: boolean | null;
  building_value_share: number | null;
  flags: Flag[];
  score: number | null;
  score_reasons: string[] | null;
  score_parts: Record<string, number> | null;
}

export interface SiteFeature {
  type: "Feature";
  properties: SiteProps;
  geometry: GeoJSON.Geometry;
}

export interface RulesFile {
  generated_at: string;
  disclaimer: string;
  assumptions: Record<string, string | number>;
  score_weights: Record<string, number>;
  score_caps: Record<string, number>;
  zones: Record<string, ApprovedZone>;
}

// NJ MOD-IV property classes.
export const PROP_CLASSES: Record<string, string> = {
  "1": "Vacant land",
  "2": "Residential (1–4 units)",
  "4A": "Commercial",
  "4B": "Industrial",
  "4C": "Apartments (5+ units)",
  "5A": "Railroad",
  "15": "Tax-exempt",
};
export const classGroup = (c: string | null) => (c ? (c.startsWith("15") ? "15" : c) : "");

export interface Filters {
  zones: string[];          // empty = all
  classes: string[];        // empty = all
  minUnusedUnits: number;
  minUnusedStories: number;
  minLotArea: number;
  maxImprLandRatio: number | null; // null = no limit
  hideHistoric: boolean;
  hideRedev: boolean;
  hideNonconforming: boolean;
  includeCondos: boolean;
  includeUnscored: boolean;
  scoreMin: number;
  scoreMax: number;
  search: string;
}

export const DEFAULT_FILTERS: Filters = {
  zones: [], classes: [], minUnusedUnits: 0, minUnusedStories: 0, minLotArea: 0, maxImprLandRatio: null,
  hideHistoric: false, hideRedev: false, hideNonconforming: false, includeCondos: false, includeUnscored: false,
  scoreMin: 0, scoreMax: 100, search: "",
};

export const imprLandRatio = (p: SiteProps) =>
  p.land_value && p.land_value > 0 && p.impr_value != null ? p.impr_value / p.land_value : null;

export function matches(p: SiteProps, f: Filters): boolean {
  if (p.status === "condo_building" && !f.includeCondos) return false;
  if (p.status === "rules_not_loaded" && !f.includeUnscored) return false;
  if (f.zones.length && !f.zones.includes(p.zone_key ?? "")) return false;
  if (f.classes.length && !f.classes.includes(classGroup(p.prop_class))) return false;
  if (f.search) {
    const q = f.search.toLowerCase();
    const hay = `${p.location ?? ""} ${p.block}/${p.lot} block ${p.block} lot ${p.lot}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  if (f.hideHistoric && p.in_historic_district) return false;
  if (f.hideRedev && (p.in_redev_area || p.has_redev_agreement)) return false;
  if (f.hideNonconforming && p.nonconforming) return false;
  // Numeric filters only constrain scored sites (others have no potential numbers).
  if (p.status === "scored") {
    if (f.minUnusedUnits > 0 && (p.unused_units ?? 0) < f.minUnusedUnits) return false;
    if (f.minUnusedStories > 0 && (p.unused_stories ?? 0) < f.minUnusedStories) return false;
    const s = p.score ?? 0;
    if (s < f.scoreMin || s > f.scoreMax) return false;
  }
  if (f.minLotArea > 0 && (p.lot_area ?? 0) < f.minLotArea) return false;
  if (f.maxImprLandRatio != null) {
    const r = imprLandRatio(p);
    if (r == null || r > f.maxImprLandRatio) return false;
  }
  return true;
}

export const fmtNum = (v: number | null | undefined, d = 0) =>
  v == null ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: d });
export const fmtMoney = (v: number | null | undefined) =>
  v == null ? "—" : `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

export const STATUS_LABEL: Record<SiteStatus, string> = {
  scored: "Scored",
  condo_building: "Condo building (not scored)",
  rules_not_loaded: "Zone rules not loaded (not scored)",
};

export function toCsv(rows: SiteProps[], disclaimer: string): string {
  const cols: [string, (p: SiteProps) => unknown][] = [
    ["block", (p) => p.block], ["lot", (p) => p.lot], ["location", (p) => p.location],
    ["zone", (p) => p.zone_key], ["class", (p) => p.prop_class], ["status", (p) => p.status],
    ["score", (p) => p.score], ["existing_stories", (p) => p.existing_stories],
    ["allowed_stories", (p) => p.allowed_stories], ["unused_stories", (p) => p.unused_stories],
    ["existing_units", (p) => p.existing_units], ["allowed_units", (p) => p.allowed_units],
    ["unused_units", (p) => p.unused_units], ["lot_area_sqft", (p) => p.lot_area],
    ["land_value", (p) => p.land_value], ["improvement_value", (p) => p.impr_value],
    ["year_built", (p) => p.year_built], ["flags", (p) => p.flags.map((f) => f.code).join(" ")],
    ["score_reasons", (p) => (p.score_reasons ?? []).join("; ")],
    ["units_formula", (p) => p.units_formula], ["stories_formula", (p) => p.stories_formula],
  ];
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [`# ${disclaimer}`, cols.map((c) => c[0]).join(","),
    ...rows.map((p) => cols.map(([, f]) => esc(f(p))).join(","))].join("\n");
}

// Score colour ramp (map + badges). Low → high.
export const SCORE_STOPS: [number, string][] = [
  [0, "#e2e8f0"], [10, "#bfdbfe"], [25, "#60a5fa"], [40, "#2563eb"], [60, "#f59e0b"], [75, "#dc2626"],
];
export const scoreColor = (s: number | null) => {
  if (s == null) return "#cbd5e1";
  let c = SCORE_STOPS[0][1];
  for (const [t, col] of SCORE_STOPS) if (s >= t) c = col;
  return c;
};
