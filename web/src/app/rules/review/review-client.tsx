"use client";

// Local-only review page: inspect extracted zone rules with their quotes, edit, approve.
// Only approved rules (data/rules/hoboken_rules.json) are used in calculations.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  DISCLAIMER, FIELDS, GRID_FIELDS,
  type ApprovedDistrict, type ApprovedValue, type ApprovedZone, type Evidence,
  type ExtractedDistrict, type ExtractedZone, type RulesPayload,
} from "@/lib/rules";

const fmt = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : String(v).replaceAll("_", " "));

function densityLabel(e?: Evidence | ApprovedDistrict["density_structured"] | null) {
  if (!e || !e.type) return "—";
  if (e.type === "site_area_per_unit") return `1 unit / ${e.site_area_per_unit_sqft ?? "?"} sf`;
  if (e.type === "units_per_acre") return `${e.units_per_acre ?? "?"} u/acre`;
  if (e.type === "max_units") return `max ${e.max_units ?? "?"} units`;
  return e.type;
}

type ZoneStatus = "approved" | "extracted" | "needs sources" | "pending";
function zoneStatus(key: string, data: RulesPayload): ZoneStatus {
  if (data.approved.zones[key]) return "approved";
  const z = data.extracted?.zones[key];
  if (!z || z.status === "no_sources") return "needs sources";
  return z.status === "extracted" ? "extracted" : "pending";
}

const statusStyle: Record<ZoneStatus, string> = {
  approved: "bg-emerald-100 text-emerald-800 border-emerald-200",
  extracted: "bg-amber-100 text-amber-800 border-amber-200",
  "needs sources": "bg-slate-100 text-slate-600 border-slate-200",
  pending: "bg-slate-100 text-slate-600 border-slate-200",
};

export default function RulesReviewPage() {
  const [data, setData] = useState<RulesPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async () => {
    const r = await fetch("/api/rules", { cache: "no-store" });
    if (!r.ok) return setError((await r.json()).error ?? r.statusText);
    setData(await r.json());
  }, []);
  useEffect(() => {
    load();
    setSelected(new URLSearchParams(window.location.search).get("zone")); // deep link: ?zone=R-1
  }, [load]);

  if (error) return <main className="p-8 text-red-700">{error}</main>;
  if (!data) return <main className="p-8 text-slate-500">Loading rules…</main>;

  const keys = data.manifest.map((m) => m.zone_key);
  const counts = keys.reduce<Record<string, number>>((acc, k) => {
    const s = zoneStatus(k, data);
    acc[s] = (acc[s] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <main className="mx-auto max-w-[1400px] space-y-6 p-4 md:p-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Zone rules review</h1>
        <p className="text-sm text-slate-600">
          Local only. Extracted values with their quotes; approve each zone to use it in calculations.
          Unapproved zones show “rules not verified”. Model: {data.extracted?.model ?? "—"}, extracted{" "}
          {data.extracted?.generated_at?.slice(0, 10) ?? "—"}.
        </p>
        <div className="flex flex-wrap gap-2 pt-1 text-xs">
          {(Object.keys(statusStyle) as ZoneStatus[]).map((s) => (
            <span key={s} className={`rounded border px-2 py-0.5 ${statusStyle[s]}`}>{s}: {counts[s] ?? 0}</span>
          ))}
        </div>
      </header>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">Zones × key fields</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase text-slate-500">
                <th className="py-2 pr-3">Zone</th>
                <th className="pr-3">Status</th>
                {GRID_FIELDS.map((f) => (
                  <th key={f} className="pr-3">{FIELDS.find((x) => x.key === f)?.label ?? "Density"}</th>
                ))}
                <th className="pr-3">Flags</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => {
                const ez = data.extracted?.zones[k];
                const az = data.approved.zones[k];
                const st = zoneStatus(k, data);
                const d0 = ez?.districts[0];
                return (
                  <tr key={k} onClick={() => setSelected(k)}
                      className={`cursor-pointer border-b hover:bg-slate-50 ${selected === k ? "bg-sky-50" : ""}`}>
                    <td className="py-2 pr-3 font-medium">{k}</td>
                    <td className="pr-3"><span className={`rounded border px-1.5 py-0.5 text-xs ${statusStyle[st]}`}>{st}</span></td>
                    {GRID_FIELDS.map((f) => {
                      const av = az?.districts[0];
                      const val = f === "density_structured"
                        ? densityLabel(av ? av.density_structured : d0?.fields[f])
                        : fmt(av ? av.fields[f]?.value : d0?.fields[f]?.value);
                      const ev = d0?.fields[f];
                      return (
                        <td key={f} className="pr-3">
                          <span title={ev?.quote ?? ""} className={ev && ev.verified === false ? "text-red-700" : ""}>{val}</span>
                        </td>
                      );
                    })}
                    <td className="pr-3 text-xs text-slate-600">
                      {(ez?.districts.length ?? 0) > 1 && <span className="mr-2">{ez!.districts.length} sub-districts</span>}
                      {ez?.districts.some((d) => d.conflicts.length) && <span className="mr-2 text-amber-700">sources disagree</span>}
                      {ez?.seed_check && !ez.seed_check.agrees && <span className="mr-2 text-amber-700">≠ seed</span>}
                      {(ez?.missing_sources.length ?? 0) > 0 && <span className="text-slate-500">{ez!.missing_sources.length} source(s) to save</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {selected && (
        <ZoneEditor key={selected + (data.approved.zones[selected]?.approved_at ?? "")}
                    zoneKey={selected} data={data} onSaved={load} />
      )}
      <p className="text-xs text-slate-500">{DISCLAIMER}</p>
    </main>
  );
}

// ---------------------------------------------------------------------------------- editor
function draftFromExtracted(d: ExtractedDistrict): ApprovedDistrict {
  const fields: Record<string, ApprovedValue> = {};
  for (const f of FIELDS) {
    const e = d.fields[f.key];
    fields[f.key] = {
      value: e?.value ?? null, basis: "extracted", quote: e?.quote ?? null,
      source_url: e?.source_url ?? null, source_type: e?.source_type ?? null, extracted_value: e?.value ?? null,
    };
  }
  const ds = d.fields["density_structured"];
  return {
    name: d.name,
    fields,
    density_structured: ds ? {
      type: ds.type ?? null, site_area_per_unit_sqft: ds.site_area_per_unit_sqft ?? null,
      units_per_acre: ds.units_per_acre ?? null, max_units: ds.max_units ?? null, rounding: ds.rounding ?? null,
      basis: "extracted", quote: ds.quote ?? null, source_url: ds.source_url ?? null,
    } : null,
    special_conditions: d.special_conditions,
  };
}

function ZoneEditor({ zoneKey, data, onSaved }: { zoneKey: string; data: RulesPayload; onSaved: () => void }) {
  const ez: ExtractedZone | undefined = data.extracted?.zones[zoneKey];
  const az = data.approved.zones[zoneKey];
  const label = ez?.label ?? data.manifest.find((m) => m.zone_key === zoneKey)?.label ?? zoneKey;

  const initial = useMemo<ApprovedDistrict[]>(
    () => az?.districts ?? ez?.districts.map(draftFromExtracted) ?? [],
    [az, ez],
  );
  const [districts, setDistricts] = useState<ApprovedDistrict[]>(initial);
  const [notes, setNotes] = useState(az?.reviewer_notes ?? "");
  const [msg, setMsg] = useState<string | null>(null);

  const setField = (di: number, key: string, raw: string, kind: string) => {
    setDistricts((prev) => prev.map((d, i) => {
      if (i !== di) return d;
      const cur = d.fields[key];
      const value = raw === "" ? null : kind === "number" ? Number(raw) : raw;
      const changed = String(value ?? "") !== String(cur.extracted_value ?? "");
      return { ...d, fields: { ...d.fields, [key]: { ...cur, value, basis: changed ? "confirmed_on_review" : "extracted" } } };
    }));
  };
  const setNote = (di: number, key: string, note: string) =>
    setDistricts((prev) => prev.map((d, i) => i !== di ? d : { ...d, fields: { ...d.fields, [key]: { ...d.fields[key], note } } }));
  const setDensity = (di: number, patch: Partial<NonNullable<ApprovedDistrict["density_structured"]>>) =>
    setDistricts((prev) => prev.map((d, i) => i !== di ? d : {
      ...d,
      density_structured: {
        type: null, site_area_per_unit_sqft: null, units_per_acre: null, max_units: null, rounding: null,
        ...(d.density_structured ?? {}), ...patch, basis: "confirmed_on_review",
      },
    }));

  const post = async (body: object) => {
    setMsg(null);
    const r = await fetch("/api/rules", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) return setMsg((await r.json()).error ?? "save failed");
    setMsg("Saved.");
    onSaved();
  };
  const approve = () => {
    const missingNote = districts.flatMap((d) => Object.entries(d.fields)
      .filter(([, v]) => v.basis === "confirmed_on_review" && !v.note?.trim()).map(([k]) => `${d.name ?? zoneKey}: ${k}`));
    if (missingNote.length) return setMsg(`Add a note (where you confirmed it) for edited values: ${missingNote.join(", ")}`);
    const zone: ApprovedZone = {
      zone_key: zoneKey, label, kind: ez?.kind ?? "", approved_by: "manual",
      approved_at: "", reviewer_notes: notes, districts,
    };
    post({ action: "approve", zone });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="text-lg">{zoneKey} <span className="font-normal text-slate-500">— {label}</span></CardTitle>
          <p className="mt-1 text-sm text-slate-600">
            {az ? <>Approved {az.approved_at} by {az.approved_by}.</> : "Not approved: shows “rules not verified” in the app."}
            {ez?.plan_type && <> Plan type: {ez.plan_type}.</>}
          </p>
        </div>
        <div className="flex gap-2">
          {az && <Button variant="outline" onClick={() => post({ action: "revoke", zone_key: zoneKey })}>Revoke approval</Button>}
          <Button onClick={approve} disabled={!districts.length}>{az ? "Save & re-approve" : "Approve zone"}</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {msg && <p className="rounded bg-slate-100 px-3 py-2 text-sm">{msg}</p>}

        <section className="grid gap-4 md:grid-cols-2">
          <div>
            <h3 className="mb-1 text-sm font-semibold">Sources used</h3>
            {ez?.sources.length ? (
              <ul className="space-y-1 text-sm">
                {ez.sources.map((s) => (
                  <li key={s.sid}><Badge variant="outline" className="mr-2">{s.sid} · {s.type}</Badge>
                    <a href={s.url} target="_blank" rel="noreferrer" className="break-all text-sky-700 underline">{s.url}</a></li>
                ))}
              </ul>
            ) : <p className="text-sm text-slate-500">None yet.</p>}
          </div>
          <div>
            <h3 className="mb-1 text-sm font-semibold">Sources still to save (manual)</h3>
            {ez?.missing_sources.length ? (
              <ul className="space-y-1 text-sm">
                {ez.missing_sources.map((s) => (
                  <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer" className="break-all text-sky-700 underline">{s.type}</a>
                    {" → "}<code className="text-xs">{s.save_as}</code></li>
                ))}
              </ul>
            ) : <p className="text-sm text-slate-500">All available.</p>}
            <p className="mt-1 text-xs text-slate-500">Then run <code>python -m pipeline.rules_fetch</code> and <code>python -m pipeline.rules_extract --zone &quot;{zoneKey}&quot;</code>.</p>
          </div>
        </section>

        {ez?.seed_check && (
          <section className={`rounded border p-3 text-sm ${ez.seed_check.agrees ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
            <b>Seed check</b> ({ez.seed_check.source}): “{ez.seed_check.text}”.{" "}
            {ez.seed_check.agrees ? "Extracted values agree." : (
              <>Differs from extraction:{" "}
                {Object.entries(ez.seed_check.differences).map(([k, v]) => (
                  <span key={k} className="mr-3"><code>{k}</code>: seed {fmt(v.seed)} vs extracted {fmt(v.extracted)}</span>
                ))}
                <span className="block text-xs text-slate-600">Check the ordinance text to decide which is correct.</span>
              </>
            )}
          </section>
        )}

        {districts.map((d, di) => {
          const ed = ez?.districts.find((x) => (x.name ?? "") === (d.name ?? ""));
          return (
            <section key={di} className="space-y-2">
              {(districts.length > 1 || d.name) && <h3 className="font-semibold">Sub-district: {d.name ?? "(base)"}</h3>}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase text-slate-500">
                      <th className="w-48 py-2 pr-3">Field</th><th className="w-56 pr-3">Value</th>
                      <th className="pr-3">Evidence (quote · source)</th><th className="w-56 pr-3">Review note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {FIELDS.map((f) => {
                      const v = d.fields[f.key];
                      const ev = ed?.fields[f.key];
                      const edited = v?.basis === "confirmed_on_review";
                      return (
                        <tr key={f.key} className="border-b align-top">
                          <td className="py-2 pr-3">
                            <div className="font-medium">{f.label}</div>
                            {f.unit && <div className="text-xs text-slate-500">{f.unit}</div>}
                          </td>
                          <td className="py-2 pr-3">
                            {f.kind === "enum" ? (
                              <select className="h-9 w-full rounded-md border px-2 text-sm" value={(v?.value as string) ?? ""}
                                      onChange={(e) => setField(di, f.key, e.target.value, f.kind)}>
                                <option value="">— not stated —</option>
                                {f.options!.map((o) => <option key={o} value={o}>{o.replaceAll("_", " ")}</option>)}
                              </select>
                            ) : f.kind === "text" ? (
                              <Textarea rows={2} value={(v?.value as string) ?? ""} onChange={(e) => setField(di, f.key, e.target.value, f.kind)} />
                            ) : (
                              <Input type="number" value={v?.value ?? ""} onChange={(e) => setField(di, f.key, e.target.value, f.kind)} />
                            )}
                            <div className="mt-1 flex flex-wrap gap-1">
                              {edited && <Badge className="bg-sky-100 text-sky-800">edited · was {fmt(v.extracted_value)}</Badge>}
                              {ev?.confidence && <Badge variant="outline">{ev.confidence}</Badge>}
                              {ev && ev.verified === false && <Badge className="bg-red-100 text-red-800">{ev.issues?.join(", ")}</Badge>}
                              {ed?.conflicts.includes(f.key) && <Badge className="bg-amber-100 text-amber-800">sources disagree</Badge>}
                              {v?.value === null && <Badge variant="outline" className="text-slate-500">missing</Badge>}
                            </div>
                          </td>
                          <td className="py-2 pr-3 text-slate-700">
                            {ev?.quote ? (
                              <>
                                <q className="italic">{ev.quote}</q>
                                {ev.source_url && <> · <a className="text-sky-700 underline" href={ev.source_url} target="_blank" rel="noreferrer">{ev.source_type}</a></>}
                              </>
                            ) : <span className="text-slate-400">no quote</span>}
                            {ev?.alternatives?.map((a, i) => (
                              <div key={i} className="mt-1 text-xs text-amber-800">
                                Other source says <b>{fmt(a.value)}</b>: <q>{a.quote}</q>
                                {a.source_url && <> · <a className="underline" href={a.source_url} target="_blank" rel="noreferrer">{a.source_type}</a></>}
                              </div>
                            ))}
                          </td>
                          <td className="py-2 pr-3">
                            <Input placeholder={edited ? "Required: where you confirmed it" : "optional"} value={v?.note ?? ""}
                                   onChange={(e) => setNote(di, f.key, e.target.value)} />
                          </td>
                        </tr>
                      );
                    })}
                    <tr className="border-b align-top">
                      <td className="py-2 pr-3 font-medium">Density (structured)</td>
                      <td className="py-2 pr-3" colSpan={2}>
                        <div className="flex flex-wrap items-center gap-2">
                          <select className="h-9 rounded-md border px-2" value={d.density_structured?.type ?? ""}
                                  onChange={(e) => setDensity(di, { type: e.target.value || null })}>
                            <option value="">— none —</option>
                            {["site_area_per_unit", "units_per_acre", "max_units", "formula", "none"].map((o) => <option key={o}>{o}</option>)}
                          </select>
                          <label className="text-xs">sf / unit <Input className="inline h-8 w-24" type="number" value={d.density_structured?.site_area_per_unit_sqft ?? ""}
                                 onChange={(e) => setDensity(di, { site_area_per_unit_sqft: e.target.value ? Number(e.target.value) : null })} /></label>
                          <label className="text-xs">units / acre <Input className="inline h-8 w-20" type="number" value={d.density_structured?.units_per_acre ?? ""}
                                 onChange={(e) => setDensity(di, { units_per_acre: e.target.value ? Number(e.target.value) : null })} /></label>
                          <select className="h-9 rounded-md border px-2 text-xs" value={d.density_structured?.rounding ?? ""}
                                  onChange={(e) => setDensity(di, { rounding: e.target.value || null })}>
                            <option value="">rounding?</option>
                            {["nearest", "down", "up", "not_stated"].map((o) => <option key={o}>{o}</option>)}
                          </select>
                        </div>
                        {d.density_structured?.quote && <p className="mt-1 text-slate-700"><q className="italic">{d.density_structured.quote}</q></p>}
                      </td>
                      <td />
                    </tr>
                  </tbody>
                </table>
              </div>
              {d.special_conditions.length > 0 && (
                <div>
                  <h4 className="mb-1 text-sm font-semibold">Special conditions</h4>
                  <ul className="space-y-1 text-sm">
                    {d.special_conditions.map((s, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <Badge variant="outline">{s.category}</Badge>
                        <span>{s.text}{s.quote && <span className="text-slate-500"> — <q className="italic">{s.quote}</q></span>}
                          {s.verified === false && <Badge className="ml-1 bg-red-100 text-red-800">quote not found</Badge>}</span>
                        <button className="ml-auto text-xs text-slate-500 hover:text-red-700"
                                onClick={() => setDistricts((prev) => prev.map((x, j) => j !== di ? x : { ...x, special_conditions: x.special_conditions.filter((_, k) => k !== i) }))}>
                          remove
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          );
        })}

        <div>
          <h3 className="mb-1 text-sm font-semibold">Reviewer notes</h3>
          <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Anything to remember about this zone" />
        </div>
      </CardContent>
    </Card>
  );
}
