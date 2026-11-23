// Shared types and field metadata for zone rules (mirrors pipeline/rules_schema.py).

export type Confidence = "high" | "medium" | "low" | null;

export interface Evidence {
  value: string | number | null;
  quote?: string | null;
  source_id?: string | null;
  source_url?: string | null;
  source_type?: string | null;
  confidence?: Confidence;
  verified?: boolean;
  issues?: string[];
  alternatives?: Evidence[];
  // density_structured extras
  type?: string | null;
  site_area_per_unit_sqft?: number | null;
  units_per_acre?: number | null;
  max_units?: number | null;
  rounding?: string | null;
}

export interface SpecialCondition {
  category: string;
  text: string;
  quote?: string | null;
  source_url?: string | null;
  verified?: boolean;
}

export interface ExtractedDistrict {
  name: string | null;
  fields: Record<string, Evidence>;
  conflicts: string[];
  special_conditions: SpecialCondition[];
}

export interface ExtractedZone {
  zone_key: string;
  label: string;
  kind: string;
  plan_type?: string | null;
  status: "extracted" | "no_sources" | "llm_pending" | "llm_failed";
  sources: { sid: string; type: string; url: string; local_path: string; chars: number }[];
  missing_sources: { type: string; url: string; save_as?: string }[];
  districts: ExtractedDistrict[];
  seed_check?: {
    source: string;
    text: string;
    values: Record<string, unknown>;
    agrees: boolean;
    differences: Record<string, { seed: unknown; extracted: unknown }>;
  } | null;
}

/** A value as stored in the approved rules file: always carries its basis. */
export interface ApprovedValue {
  value: string | number | null;
  basis: "extracted" | "confirmed_on_review";
  quote?: string | null;
  source_url?: string | null;
  source_type?: string | null;
  extracted_value?: string | number | null;
  note?: string;
}

export interface ApprovedDistrict {
  name: string | null;
  fields: Record<string, ApprovedValue>;
  density_structured: {
    type: string | null;
    site_area_per_unit_sqft: number | null;
    units_per_acre: number | null;
    max_units: number | null;
    rounding: string | null;
    basis: "extracted" | "confirmed_on_review";
    quote?: string | null;
    source_url?: string | null;
  } | null;
  special_conditions: SpecialCondition[];
}

export interface ApprovedZone {
  zone_key: string;
  label: string;
  kind: string;
  approved_by: "manual";
  approved_at: string; // YYYY-MM-DD
  reviewer_notes: string;
  districts: ApprovedDistrict[];
}

export interface RulesPayload {
  extracted: { generated_at: string; model: string; zones: Record<string, ExtractedZone> } | null;
  approved: { updated_at: string; zones: Record<string, ApprovedZone> };
  manifest: { zone_key: string; label: string; kind: string }[];
}

export type FieldKind = "number" | "text" | "enum";
export const FIELDS: { key: string; label: string; kind: FieldKind; unit?: string; options?: string[] }[] = [
  { key: "residential_permitted", label: "Residential permitted", kind: "enum", options: ["yes", "no", "conditional"] },
  { key: "max_height_ft", label: "Max height", kind: "number", unit: "ft" },
  { key: "max_stories", label: "Max stories", kind: "number" },
  { key: "height_measured_from", label: "Height measured from", kind: "enum", options: ["grade", "design_flood_elevation", "other"] },
  { key: "height_limits_combine", label: "Height limits combine", kind: "enum", options: ["whichever_is_less", "both_apply", "not_stated"] },
  { key: "height_rule_text", label: "Height rule (as written)", kind: "text" },
  { key: "min_lot_area_sqft", label: "Min lot area", kind: "number", unit: "sq ft" },
  { key: "min_lot_width_ft", label: "Min lot width", kind: "number", unit: "ft" },
  { key: "min_lot_depth_ft", label: "Min lot depth", kind: "number", unit: "ft" },
  { key: "max_lot_coverage_pct", label: "Max lot coverage", kind: "number", unit: "%" },
  { key: "max_far", label: "Max FAR", kind: "number" },
  { key: "min_floor_to_floor_ft", label: "Min floor-to-floor", kind: "number", unit: "ft" },
  { key: "density_rule_text", label: "Density rule (as written)", kind: "text" },
];

export const GRID_FIELDS = ["max_height_ft", "max_stories", "height_measured_from", "max_lot_coverage_pct", "min_lot_area_sqft", "density_structured"];

export const DISCLAIMER = "Estimate based on public zoning text; verify with the Hoboken Zoning Office.";
