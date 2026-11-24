import { promises as fs } from "fs";
import path from "path";
import type { RulesFile } from "@/lib/sites";

export const metadata = { title: "About — Zoning Upside" };

export default async function AboutPage() {
  const rules: RulesFile = JSON.parse(await fs.readFile(path.join(process.cwd(), "public", "data", "rules.json"), "utf8"));
  const w = rules.score_weights;
  return (
    <article className="mx-auto w-full max-w-3xl space-y-6 p-6 text-sm leading-relaxed text-slate-700">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">About Zoning Upside</h1>
        <p className="mt-2">
          Zoning Upside finds Hoboken properties where the zoning appears to allow a bigger building, with more floors or more
          apartments, than the one standing there today. Every result shows the rule text and source it is based on.
        </p>
        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">{rules.disclaimer}</p>
      </header>

      <S title="Method">
        <ol className="list-decimal space-y-1 pl-5">
          <li><b>Existing building.</b> Floors, apartments and lot size are read from the City&apos;s public tax records (MOD-IV), e.g. “3F-2U” = 3 floors, 2 units. Codes that can&apos;t be read are left blank, never guessed.</li>
          <li><b>Sites.</b> Condo units are grouped into buildings (not scored), and properties repeated across several lots are merged.</li>
          <li><b>Zone and constraints.</b> Each site gets the zoning district covering most of it, plus flags for historic districts, flood zones, redevelopment areas and agreements (a layer must cover at least 10% of the lot).</li>
          <li><b>Rules.</b> An AI model read the City&apos;s Zoning Guide and returned each rule with a verbatim quote. Code checked every quote against the source, and a person approved each zone.</li>
          <li><b>Allowed.</b> Residential/mixed-use limits are used first; if a zone states only commercial limits, those are used and flagged. Floors = the zone&apos;s story limit, checked against height ÷ the zone&apos;s minimum floor height. Where a zone gives only a height (R-2, R-3, C-2), floors are estimated at a realistic {String(rules.assumptions.typical_floor_to_floor_ft)} ft per floor (40 ft → 3), and the minimum-floor-height result (40 ft → 4) is shown as the theoretical maximum. Units = lot area ÷ the zone&apos;s square feet per unit, rounded as the rule says (down when not stated).</li>
          <li><b>Score (0–100).</b> Unused units +{w.unused_units}, unused floors +{w.unused_stories}, lot size +{w.lot_area}, land-driven value +{w.land_value_share}, older building +{w.old_building}, vacant land +{w.vacant_land}; historic {w.historic}, redevelopment agreement {w.redev_agreement}, nonconforming {w.nonconforming}, irregular lot {w.irregular_lot}, tax-exempt {w.exempt}, possibly under construction (“WIP”, “GUTTED”… in the tax record) {w.under_construction}, building detected on a lot the tax record calls empty {w.building_detected}. Exempt, possibly-under-construction and possible condo master lots are hidden by default.</li>
          <li><b>Cross-check.</b> Building footprints from Overture Maps (OpenStreetMap, USGS Lidar heights, Microsoft ML footprints) are overlaid on each lot. If the tax record says vacant, 0 floors or parking lot but footprints cover at least {String(rules.assumptions.building_detected_coverage_pct)}% of the lot, the site is flagged “Building detected — tax record may be outdated”. If tax floors and footprint floors (stated, or height ÷ {String(rules.assumptions.typical_floor_to_floor_ft)} ft) differ by {String(rules.assumptions.floors_disagree_min)} or more, both are shown.</li>
        </ol>
      </S>

      <S title="Data sources">
        <ul className="list-disc space-y-1 pl-5">
          <li>City of Hoboken ArcGIS services: zoning districts, redevelopment and rehabilitation areas, zoning in progress, redevelopment agreements, historic districts, FEMA advisory flood zones.</li>
          <li>Hoboken parcel layer (ArcGIS service hosted by Civil Solutions): lot shapes with NJ MOD-IV tax record fields.</li>
          <li>City of Hoboken Zoning Guide (zone pages).</li>
          <li>Overture Maps building footprints (CDLA Permissive 2.0 / ODbL), release {rules.data_dates?.overture_release ?? "—"}.</li>
          <li>Basemap © OpenStreetMap contributors, tiles by OpenFreeMap.</li>
        </ul>
        <p className="mt-2"><b>Privacy:</b> owner names and mailing addresses are never requested, stored or shown.</p>
      </S>

      <S title="Coverage">
        <p>Rules are loaded for {Object.keys(rules.zones).sort().join(", ")} — about 90% of non-condo properties. Industrial zones,
          the university and waterfront districts, and redevelopment plan areas are shown in grey and not scored yet.</p>
      </S>

      <S title="Limitations">
        <ul className="list-disc space-y-1 pl-5">
          <li>These are estimates from public zoning text, not legal answers. Variances, site plan review, parking, setbacks, flood-elevation rules and historic review can all change what can be built.</li>
          <li>Tax building descriptions can be outdated or incomplete, so “existing” floors and units may be wrong. The footprint cross-check catches some of this, but footprint data has its own gaps and lags.</li>
          <li>Floors are estimated at {String(rules.assumptions.typical_floor_to_floor_ft)} ft per floor where a zone has no story limit; the theoretical maximum at the minimum floor height is also shown.</li>
          <li>Year built is often a default value in the tax data (many records show 1901).</li>
          <li>Sub-districts (e.g. C-2 Court Street) can&apos;t be located on the map; affected sites are flagged.</li>
          <li>Lot coverage of the existing building is not in the data, so only the allowed coverage is shown.</li>
          <li>On large sites (≥ {String(rules.assumptions.large_site_sqft)} sq ft) density alone overstates potential: parking, setbacks, open space and site plan review usually reduce the unit count.</li>
          <li>Where sources disagree (e.g. C-1 height: Zoning Guide 60 ft vs. ordinance text 52 ft), the approved value is used and the disagreement is shown.</li>
        </ul>
      </S>

      <S title="Roadmap">
        <ul className="list-disc space-y-1 pl-5">
          <li>Load the remaining zones and redevelopment plans from the ordinance and plan PDFs.</li>
          <li>Nearby Planning and Zoning Board approvals that exceeded zoning.</li>
          <li>Cross-check floors against building heights from open map data.</li>
          <li>Jersey City and other towns.</li>
        </ul>
      </S>
      <S title="Data dates">
        <ul className="list-disc space-y-1 pl-5">
          <li>Tax data (parcels) downloaded {rules.data_dates?.tax_data ?? "—"}</li>
          <li>Zoning layers downloaded {rules.data_dates?.zoning_layers ?? "—"}; Zoning Guide pages downloaded {rules.data_dates?.zoning_guide ?? "—"}</li>
          <li>Building footprints: Overture release {rules.data_dates?.overture_release ?? "—"} (downloaded {rules.data_dates?.overture_downloaded ?? "—"})</li>
          <li>Scores generated {rules.generated_at}</li>
        </ul>
      </S>
    </article>
  );
}

const S = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section><h2 className="mb-2 text-base font-semibold text-slate-900">{title}</h2>{children}</section>
);
