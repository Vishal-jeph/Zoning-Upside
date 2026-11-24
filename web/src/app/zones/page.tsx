// Approved zone rules with their citations (read at build time from public/data/rules.json).
import { promises as fs } from "fs";
import path from "path";
import { ExternalLink } from "lucide-react";
import { FIELDS } from "@/lib/rules";
import type { RulesFile } from "@/lib/sites";

export const metadata = { title: "Zone rules — Zoning Upside" };

const COLS = ["max_height_ft", "max_stories", "height_measured_from", "min_floor_to_floor_ft", "max_lot_coverage_pct", "min_lot_area_sqft"];

export default async function ZonesPage() {
  const rules: RulesFile = JSON.parse(await fs.readFile(path.join(process.cwd(), "public", "data", "rules.json"), "utf8"));
  const label = (k: string) => FIELDS.find((f) => f.key === k)?.label ?? k;
  const unit = (k: string) => FIELDS.find((f) => f.key === k)?.unit ?? "";
  const zones = Object.values(rules.zones).sort((a, b) => a.zone_key.localeCompare(b.zone_key));

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Zone rules</h1>
        <p className="mt-1 text-sm text-slate-600">
          Rules used in the calculations. Each value was extracted from the City of Hoboken Zoning Guide with its exact quote,
          checked automatically against the source text, and approved by a person. Only these zones are scored.
        </p>
        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">{rules.disclaimer}</p>
      </div>

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-600">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Zone</th>
              {COLS.map((c) => <th key={c} className="px-3 py-2 text-right font-medium">{label(c)}</th>)}
              <th className="px-3 py-2 text-right font-medium">Density</th>
              <th className="px-3 py-2 text-left font-medium">Approved</th>
            </tr>
          </thead>
          <tbody>
            {zones.flatMap((z) => z.districts.map((d) => (
              <tr key={`${z.zone_key}-${d.name}`} className="border-t">
                <td className="px-3 py-1.5 font-medium"><a href={`#${z.zone_key}`} className="hover:underline">{z.label}{d.name ? ` · ${d.name}` : ""}</a></td>
                {COLS.map((c) => {
                  const v = d.fields[c]?.value;
                  return <td key={c} className="px-3 py-1.5 text-right tabular-nums">{v == null || v === "" ? <span className="text-slate-400">—</span> : `${String(v).replace(/_/g, " ")}${unit(c) ? ` ${unit(c)}` : ""}`}</td>;
                })}
                <td className="px-3 py-1.5 text-right">{d.density_structured?.site_area_per_unit_sqft
                  ? `${d.density_structured.site_area_per_unit_sqft} sq ft/unit` : <span className="text-slate-400">{d.density_structured?.type ?? "—"}</span>}</td>
                <td className="px-3 py-1.5 text-xs text-slate-500">{z.approved_at}</td>
              </tr>
            )))}
          </tbody>
        </table>
      </div>

      {zones.map((z) => (
        <section key={z.zone_key} id={z.zone_key} className="scroll-mt-4 space-y-3 rounded-md border p-4">
          <h2 className="text-lg font-semibold">{z.label} <span className="text-xs font-normal text-slate-500">approved {z.approved_at}</span></h2>
          {z.districts.map((d) => (
            <div key={d.name ?? "main"} className="space-y-2">
              {d.name && <h3 className="font-medium">Sub-district: {d.name}</h3>}
              <div className="grid gap-2 md:grid-cols-2">
                {FIELDS.filter((f) => d.fields[f.key]?.value != null && d.fields[f.key]?.value !== "" && f.kind !== "text").map((f) => {
                  const e = d.fields[f.key];
                  return (
                    <div key={f.key} className="rounded border p-2 text-xs">
                      <div className="flex justify-between"><span className="text-slate-600">{f.label}</span>
                        <span className="font-semibold">{String(e.value).replace(/_/g, " ")}{f.unit ? ` ${f.unit}` : ""}</span></div>
                      {e.quote && <blockquote className="mt-1 border-l-2 pl-2 italic text-slate-600">“{e.quote}”</blockquote>}
                      {e.source_url && <a href={e.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-sky-700 hover:underline">source <ExternalLink className="h-3 w-3" /></a>}
                    </div>
                  );
                })}
                {d.density_structured && (
                  <div className="rounded border p-2 text-xs">
                    <div className="flex justify-between"><span className="text-slate-600">Density</span>
                      <span className="font-semibold">{d.density_structured.site_area_per_unit_sqft ? `${d.density_structured.site_area_per_unit_sqft} sq ft per unit` : d.density_structured.type}</span></div>
                    {d.density_structured.quote && <blockquote className="mt-1 border-l-2 pl-2 italic text-slate-600">“{d.density_structured.quote}”</blockquote>}
                  </div>
                )}
              </div>
              {d.special_conditions.length > 0 && (
                <ul className="list-disc pl-5 text-xs text-slate-700">{d.special_conditions.map((s, i) => <li key={i}>{s.text}</li>)}</ul>
              )}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
