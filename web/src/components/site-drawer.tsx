"use client";
// Detail panel: existing vs allowed, formulas, every rule with its quote and source, flags, score reasons.
import { useState } from "react";
import { Check, Copy, ExternalLink, X } from "lucide-react";
import { FIELDS, type ApprovedDistrict } from "@/lib/rules";
import {
  PROP_CLASSES, STATUS_LABEL, classGroup, fmtMoney, fmtNum, scoreColor, type RulesFile, type SiteProps,
} from "@/lib/sites";

const PART_LABEL: Record<string, string> = {
  unused_units: "Unused units", unused_stories: "Unused floors", lot_area: "Lot size",
  land_value_share: "Land-driven value", old_building: "Older building", vacant_land: "Vacant land",
  historic: "Historic district", redev_agreement: "Redevelopment agreement", nonconforming: "Nonconforming",
  irregular_lot: "Irregular lot", exempt: "Tax-exempt",
};

export default function SiteDrawer({ site, rules, onClose }: {
  site: SiteProps; rules: RulesFile; onClose: () => void;
}) {
  const zone = site.zone_key ? rules.zones[site.zone_key] : undefined;
  const district: ApprovedDistrict | undefined = zone?.districts.find((d) => d.name === site.rule_district) ?? zone?.districts[0];
  const f = district?.fields ?? {};
  const maxCov = f.max_lot_coverage_pct?.value as number | undefined;

  return (
    <aside className="flex h-full w-full flex-col bg-white">
      <header className="flex items-start justify-between gap-2 border-b p-4">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold">{site.location ?? "No address"}</h2>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <BlockLot site={site} />
            <span>· Zone {site.zone ?? "—"}{site.rule_district ? ` (${site.rule_district})` : ""}</span>
          </div>
          <div className="mt-1 text-xs text-slate-500">{STATUS_LABEL[site.status]}</div>
        </div>
        <div className="flex items-start gap-2">
          {site.score != null && (
            <div className="rounded-md px-3 py-1 text-center" style={{ background: scoreColor(site.score), color: site.score >= 40 ? "white" : "#0f172a" }}>
              <div className="text-2xl font-bold leading-none tabular-nums">{site.score}</div>
              <div className="text-[10px] uppercase tracking-wide">score</div>
            </div>
          )}
          <button onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-slate-100"><X className="h-4 w-4" /></button>
        </div>
      </header>

      <div className="flex-1 space-y-5 overflow-y-auto p-4 text-sm">
        <p className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">{rules.disclaimer}</p>

        {site.status === "scored" && (
          <Section title="Existing vs allowed">
            <table className="w-full text-sm">
              <thead className="text-xs text-slate-500">
                <tr><th className="text-left font-medium" /><th className="text-right font-medium">Existing</th>
                  <th className="text-right font-medium">Allowed</th><th className="text-right font-medium">Unused</th></tr>
              </thead>
              <tbody className="tabular-nums">
                <Row label="Floors" a={fmtNum(site.existing_stories, 1)} b={fmtNum(site.allowed_stories, 1)} c={fmtNum(site.unused_stories, 1)} />
                <Row label="Units" a={fmtNum(site.existing_units)} b={fmtNum(site.allowed_units)} c={fmtNum(site.unused_units)} />
                <Row label="Lot coverage" a="not in data"
                     b={maxCov != null ? `${maxCov}%${site.lot_area ? ` ≈ ${fmtNum(site.lot_area * maxCov / 100)} sq ft` : ""}` : "—"} c="" />
                <Row label="Max height" a="—" b={f.max_height_ft?.value != null ? `${f.max_height_ft.value} ft` : "—"} c="" />
              </tbody>
            </table>
            {site.nonconforming && <p className="mt-2 text-xs text-red-700">The existing building already exceeds a zone limit, so this is not counted as an expansion opportunity.</p>}
          </Section>
        )}

        {site.status === "scored" && (
          <Section title="How this was calculated">
            <Calc label="Allowed floors" formula={site.stories_formula} note={site.stories_note} />
            <Calc label="Allowed units" formula={site.units_formula} note={site.units_note} />
            <Calc label="Existing units" formula={site.existing_units_basis ? `${fmtNum(site.existing_units)} — from ${site.existing_units_basis} (“${site.bldg_desc ?? ""}”)` : null}
                  note="Not readable from the tax building description." />
            <Calc label="Lot area" formula={site.lot_area ? `${fmtNum(site.lot_area)} sq ft — from ${site.lot_area_basis} (“${site.lot_desc ?? ""}”)` : null} note="Unknown." />
            <p className="text-xs text-slate-500">
              Assumptions: {String(rules.assumptions.binding_limit)} Floor-to-floor height is {String(rules.assumptions.default_floor_to_floor_ft)} ft
              when the zone states no minimum. When a rule doesn&apos;t say how to round, units are rounded {String(rules.assumptions.default_rounding)}.
            </p>
          </Section>
        )}

        {site.score_reasons && site.score_reasons.length > 0 && (
          <Section title="Why this score">
            <ul className="list-disc space-y-0.5 pl-5">{site.score_reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            {site.score_parts && (
              <div className="mt-2 grid grid-cols-2 gap-x-4 text-xs text-slate-600">
                {Object.entries(site.score_parts).map(([k, v]) => (
                  <div key={k} className="flex justify-between"><span>{PART_LABEL[k] ?? k}</span>
                    <span className={`tabular-nums ${v < 0 ? "text-red-600" : ""}`}>{v > 0 ? "+" : ""}{v}</span></div>
                ))}
              </div>
            )}
          </Section>
        )}

        {site.flags.length > 0 && (
          <Section title="Things to check">
            <ul className="space-y-1.5">
              {site.flags.map((fl) => <li key={fl.code} className="rounded bg-slate-50 p-2 text-xs">{fl.text}</li>)}
            </ul>
          </Section>
        )}

        {district && (
          <Section title={`Zone rules used — ${zone?.label}${district.name ? ` · ${district.name}` : ""}`}>
            <p className="mb-2 text-xs text-slate-500">Approved on review {zone?.approved_at}. Every value below is quoted from its source.</p>
            <div className="space-y-2">
              {FIELDS.filter((fd) => f[fd.key]?.value != null && f[fd.key]?.value !== "" && fd.kind !== "text").map((fd) => (
                <Evidence key={fd.key} label={fd.label} value={`${String(f[fd.key].value).replace(/_/g, " ")}${fd.unit ? ` ${fd.unit}` : ""}`}
                          quote={f[fd.key].quote} url={f[fd.key].source_url} />
              ))}
              {district.density_structured && (
                <Evidence label="Density" value={district.density_structured.site_area_per_unit_sqft
                  ? `${district.density_structured.site_area_per_unit_sqft} sq ft per unit` : (district.density_structured.type ?? "—")}
                          quote={district.density_structured.quote} url={district.density_structured.source_url} />
              )}
            </div>
            {district.special_conditions.length > 0 && (
              <div className="mt-3">
                <div className="mb-1 text-xs font-medium text-slate-600">Special conditions</div>
                <ul className="list-disc space-y-0.5 pl-5 text-xs">{district.special_conditions.map((s, i) => <li key={i}>{s.text}</li>)}</ul>
              </div>
            )}
          </Section>
        )}

        <Section title="Property facts (tax record)">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <Fact k="Property class" v={`${site.prop_class ?? "—"} ${PROP_CLASSES[classGroup(site.prop_class)] ? `· ${PROP_CLASSES[classGroup(site.prop_class)]}` : ""}`} />
            <Fact k="Building description" v={site.bldg_desc ?? "—"} />
            <Fact k="Lot description" v={site.lot_desc ?? "—"} />
            <Fact k="Year built" v={site.year_built ? String(site.year_built) : "—"} />
            <Fact k="Land value" v={fmtMoney(site.land_value)} />
            <Fact k="Building value" v={fmtMoney(site.impr_value)} />
            <Fact k="Building share of value" v={site.building_value_share != null ? `${Math.round(site.building_value_share * 100)}%` : "—"} />
            <Fact k="Last sale" v={site.sale_date ? `${site.sale_date} · ${fmtMoney(site.sale_price)}` : "—"} />
            {site.is_condo_building && <Fact k="Condo units" v={fmtNum(site.condo_unit_count)} />}
            {site.merged_lots && site.merged_lots.length > 0 && <Fact k="Includes lots" v={site.merged_lots.join(", ")} />}
          </dl>
        </Section>

        <Section title="Sources">
          <ul className="space-y-1 text-xs">
            <Link url={site.guide_url} label="City of Hoboken Zoning Guide page" />
            <Link url={site.ordinance_url} label="Zoning ordinance (Chapter 196)" />
            <Link url={site.redev_area_url} label="Redevelopment / rehabilitation plan" />
            <Link url={site.redev_agreement_url} label="Redevelopment agreement" />
          </ul>
        </Section>
      </div>
    </aside>
  );
}

function BlockLot({ site }: { site: SiteProps }) {
  const [done, setDone] = useState(false);
  const text = `Block ${site.block} Lot ${site.lot}`;
  return (
    <button title="Copy block/lot (for cross-referencing in Deal Finder)" className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs hover:bg-slate-200"
            onClick={() => { navigator.clipboard?.writeText(text); setDone(true); setTimeout(() => setDone(false), 1200); }}>
      {text}{done ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section><h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>{children}</section>
);
const Row = ({ label, a, b, c }: { label: string; a: string; b: string; c: string }) => (
  <tr className="border-t"><td className="py-1 text-slate-600">{label}</td><td className="py-1 text-right">{a}</td>
    <td className="py-1 text-right font-medium">{b}</td><td className="py-1 text-right font-semibold text-emerald-700">{c}</td></tr>
);
const Calc = ({ label, formula, note }: { label: string; formula: string | null; note: string | null }) => (
  <div className="mb-2"><div className="text-xs font-medium text-slate-600">{label}</div>
    <div className={formula ? "font-mono text-xs" : "text-xs italic text-slate-500"}>{formula ?? note ?? "—"}</div></div>
);
const Fact = ({ k, v }: { k: string; v: string }) => (<><dt className="text-slate-500">{k}</dt><dd className="break-words">{v}</dd></>);
const Evidence = ({ label, value, quote, url }: { label: string; value: string; quote?: string | null; url?: string | null }) => (
  <div className="rounded border p-2">
    <div className="flex justify-between gap-2 text-xs"><span className="text-slate-600">{label}</span><span className="font-semibold">{value}</span></div>
    {quote && <blockquote className="mt-1 border-l-2 border-slate-300 pl-2 text-xs italic text-slate-600">“{quote}”</blockquote>}
    {url && <a href={url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-[11px] text-sky-700 hover:underline">source <ExternalLink className="h-3 w-3" /></a>}
  </div>
);
const Link = ({ url, label }: { url: string | null; label: string }) =>
  url ? <li><a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sky-700 hover:underline">{label}<ExternalLink className="h-3 w-3" /></a></li> : null;
