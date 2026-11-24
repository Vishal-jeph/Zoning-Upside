"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Download, RotateCcw, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import SiteDrawer from "@/components/site-drawer";
import SiteTable from "@/components/site-table";
import { OVERLAYS, type OverlayKey } from "@/components/site-map";
import {
  DEFAULT_FILTERS, PROP_CLASSES, matches, toCsv, type Filters, type RulesFile, type SiteFeature,
} from "@/lib/sites";

const SiteMap = dynamic(() => import("@/components/site-map"), { ssr: false,
  loading: () => <div className="grid h-full place-items-center text-sm text-slate-500">Loading map…</div> });

export default function Explorer() {
  const [features, setFeatures] = useState<SiteFeature[] | null>(null);
  const [rules, setRules] = useState<RulesFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [overlays, setOverlays] = useState<Record<OverlayKey, boolean>>({ zoning: false, historic: false, flood: false, rehab_redev: false });
  const [showFilters, setShowFilters] = useState(true);

  useEffect(() => {
    Promise.all([fetch("/data/sites.geojson").then((r) => r.json()), fetch("/data/rules.json").then((r) => r.json())])
      .then(([s, r]) => { setFeatures(s.features); setRules(r); })
      .catch((e) => setError(String(e)));
  }, []);

  const filtered = useMemo(() => (features ?? []).filter((f) => matches(f.properties, filters)), [features, filters]);
  const rows = useMemo(() => filtered.map((f) => f.properties), [filtered]);
  const selected = useMemo(() => features?.find((f) => f.properties.site_id === selectedId)?.properties ?? null, [features, selectedId]);
  const zoneOptions = useMemo(() => {
    const c = new Map<string, number>();
    for (const f of features ?? []) if (f.properties.zone_key) c.set(f.properties.zone_key, (c.get(f.properties.zone_key) ?? 0) + 1);
    return [...c.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k);
  }, [features]);

  const set = <K extends keyof Filters>(k: K, v: Filters[K]) => setFilters((f) => ({ ...f, [k]: v }));
  const toggleIn = (k: "zones" | "classes", v: string) =>
    setFilters((f) => ({ ...f, [k]: f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v] }));

  const exportCsv = () => {
    if (!rules) return;
    const blob = new Blob([toCsv(rows, rules.disclaimer)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `hoboken-zoning-upside-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (error) return <div className="p-8 text-red-700">Could not load data: {error}</div>;

  return (
    <div className="flex min-h-0 flex-1">
      {showFilters && (
        <aside className="w-64 shrink-0 space-y-4 overflow-y-auto border-r bg-slate-50/60 p-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="font-semibold">Filters</span>
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => setFilters(DEFAULT_FILTERS)}>
              <RotateCcw className="mr-1 h-3 w-3" />Reset</Button>
          </div>
          <Input placeholder="Address or block/lot" value={filters.search} onChange={(e) => set("search", e.target.value)} className="h-8 bg-white" />

          <Group title="Score range">
            <div className="flex items-center gap-2">
              <NumIn value={filters.scoreMin} onChange={(v) => set("scoreMin", v)} />–<NumIn value={filters.scoreMax} onChange={(v) => set("scoreMax", v)} />
            </div>
          </Group>
          <Group title="Minimum upside">
            <Field label="Unused units ≥"><NumIn value={filters.minUnusedUnits} onChange={(v) => set("minUnusedUnits", v)} /></Field>
            <Field label="Unused floors ≥"><NumIn value={filters.minUnusedStories} onChange={(v) => set("minUnusedStories", v)} step={0.5} /></Field>
            <Field label="Lot size ≥ (sq ft)"><NumIn value={filters.minLotArea} onChange={(v) => set("minLotArea", v)} step={500} /></Field>
            <Field label="Building ÷ land value ≤">
              <NumIn value={filters.maxImprLandRatio ?? ""} step={0.1} placeholder="any"
                     onChange={(v, raw) => set("maxImprLandRatio", raw === "" ? null : v)} />
            </Field>
          </Group>
          <Group title="Exclude">
            <Toggle label="Historic districts" checked={filters.hideHistoric} onChange={(v) => set("hideHistoric", v)} />
            <Toggle label="Redevelopment areas & agreements" checked={filters.hideRedev} onChange={(v) => set("hideRedev", v)} />
            <Toggle label="Nonconforming buildings" checked={filters.hideNonconforming} onChange={(v) => set("hideNonconforming", v)} />
          </Group>
          <Group title="Include">
            <Toggle label="Condo buildings" checked={filters.includeCondos} onChange={(v) => set("includeCondos", v)} />
            <Toggle label="Zones without loaded rules" checked={filters.includeUnscored} onChange={(v) => set("includeUnscored", v)} />
          </Group>
          <Group title="Zone">
            <div className="grid grid-cols-2 gap-1">
              {zoneOptions.map((z) => (
                <Check key={z} label={z} checked={filters.zones.includes(z)} onChange={() => toggleIn("zones", z)}
                       dim={!!rules && !rules.zones[z]} />
              ))}
            </div>
          </Group>
          <Group title="Property class">
            {Object.entries(PROP_CLASSES).map(([k, v]) => (
              <Check key={k} label={`${k} · ${v}`} checked={filters.classes.includes(k)} onChange={() => toggleIn("classes", k)} />
            ))}
          </Group>
          <Group title="Map layers">
            {OVERLAYS.map((o) => (
              <Toggle key={o.key} label={o.label} color={o.color} checked={overlays[o.key]}
                      onChange={(v) => setOverlays((s) => ({ ...s, [o.key]: v }))} />
            ))}
          </Group>
        </aside>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b px-3 py-1.5 text-sm">
          <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => setShowFilters((s) => !s)}>
            <SlidersHorizontal className="h-4 w-4" /></Button>
          <span className="font-medium tabular-nums">{features ? `${filtered.length.toLocaleString()} sites` : "Loading…"}</span>
          {features && <span className="text-xs text-slate-500">of {features.length.toLocaleString()}</span>}
          <div className="flex-1" />
          <Button variant="outline" size="sm" className="h-7" onClick={exportCsv} disabled={!rows.length}>
            <Download className="mr-1 h-3.5 w-3.5" />CSV</Button>
        </div>
        <div className="relative min-h-0 flex-[3]">
          <SiteMap features={filtered} selectedId={selectedId} onSelect={(id) => setSelectedId(id || null)} overlays={overlays} />
        </div>
        <div className="min-h-0 flex-[2] border-t">
          <SiteTable rows={rows} selectedId={selectedId} onSelect={setSelectedId} />
        </div>
      </main>

      {selected && rules && (
        <div className="w-[420px] shrink-0 border-l shadow-xl max-md:fixed max-md:inset-0 max-md:z-30 max-md:w-full">
          <SiteDrawer site={selected} rules={rules} onClose={() => setSelectedId(null)} />
        </div>
      )}
    </div>
  );
}

const Group = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="space-y-1.5"><div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</div>{children}</div>
);
const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="flex items-center justify-between gap-2"><span className="text-xs text-slate-700">{label}</span>{children}</div>
);
function NumIn({ value, onChange, step = 1, placeholder }: {
  value: number | string; onChange: (v: number, raw: string) => void; step?: number; placeholder?: string;
}) {
  return <Input type="number" value={value} step={step} min={0} placeholder={placeholder} className="h-7 w-20 bg-white px-2 text-xs"
                onChange={(e) => onChange(Number(e.target.value) || 0, e.target.value)} />;
}
function Toggle({ label, checked, onChange, color }: { label: string; checked: boolean; onChange: (v: boolean) => void; color?: string }) {
  return (
    <Label className="flex cursor-pointer items-center justify-between gap-2 text-xs font-normal">
      <span className="flex items-center gap-1.5">{color && <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />}{label}</span>
      <Switch checked={checked} onCheckedChange={onChange} />
    </Label>
  );
}
function Check({ label, checked, onChange, dim }: { label: string; checked: boolean; onChange: () => void; dim?: boolean }) {
  return (
    <Label className={`flex cursor-pointer items-center gap-1.5 text-xs font-normal ${dim ? "text-slate-400" : ""}`}>
      <Checkbox checked={checked} onCheckedChange={onChange} />{label}
    </Label>
  );
}
