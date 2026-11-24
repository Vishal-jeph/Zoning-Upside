"use client";
// MapLibre map: sites coloured by upside score, toggleable zoning / constraint overlays, click to select.
import { useEffect, useRef, useState } from "react";
import maplibregl, { type ExpressionSpecification, type GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { SCORE_STOPS, type SiteFeature } from "@/lib/sites";

// Free, keyless vector basemap (OpenFreeMap, OpenStreetMap data).
const BASEMAP = "https://tiles.openfreemap.org/styles/positron";

export type OverlayKey = "zoning" | "historic" | "flood" | "rehab_redev";
export const OVERLAYS: { key: OverlayKey; label: string; color: string }[] = [
  { key: "zoning", label: "Zoning districts", color: "#475569" },
  { key: "historic", label: "Historic districts", color: "#b45309" },
  { key: "flood", label: "Flood zones (A/V)", color: "#0284c7" },
  { key: "rehab_redev", label: "Redevelopment areas", color: "#7c3aed" },
];

const scoreColor: ExpressionSpecification = [
  "case",
  ["==", ["get", "status"], "scored"],
  ["step", ["get", "score"], SCORE_STOPS[0][1], ...SCORE_STOPS.slice(1).flatMap(([t, c]) => [t, c])] as ExpressionSpecification,
  ["==", ["get", "status"], "condo_building"], "#e9d5ff",
  "#d4d4d8",
];

interface Props {
  features: SiteFeature[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  overlays: Record<OverlayKey, boolean>;
}

export default function SiteMap({ features, selectedId, onSelect, overlays }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<{ x: number; y: number; text: string } | null>(null);
  const fitted = useRef(false);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Create the map once.
  useEffect(() => {
    if (!box.current) return;
    const map = new maplibregl.Map({
      container: box.current, style: BASEMAP, center: [-74.0324, 40.7440], zoom: 13.6,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    map.on("load", async () => {
      map.addSource("sites", { type: "geojson", data: { type: "FeatureCollection", features: [] }, promoteId: "site_id" });
      map.addLayer({ id: "sites-fill", type: "fill", source: "sites",
        paint: { "fill-color": scoreColor, "fill-opacity": 0.85 } });
      map.addLayer({ id: "sites-line", type: "line", source: "sites",
        paint: { "line-color": "#ffffff", "line-width": 0.4 } });

      // Overlays (drawn above sites, below the selection outline).
      const load = (k: OverlayKey) => `/data/layer_${k}.geojson`;
      map.addSource("ov-flood", { type: "geojson", data: load("flood") });
      map.addLayer({ id: "ov-flood", type: "fill", source: "ov-flood", layout: { visibility: "none" },
        filter: ["in", ["slice", ["get", "zone"], 0, 1], ["literal", ["A", "V"]]],
        paint: { "fill-color": "#0284c7", "fill-opacity": 0.18 } });
      map.addSource("ov-historic", { type: "geojson", data: load("historic") });
      map.addLayer({ id: "ov-historic", type: "line", source: "ov-historic", layout: { visibility: "none" },
        paint: { "line-color": "#b45309", "line-width": 2 } });
      map.addSource("ov-rehab_redev", { type: "geojson", data: load("rehab_redev") });
      map.addLayer({ id: "ov-rehab_redev", type: "line", source: "ov-rehab_redev", layout: { visibility: "none" },
        paint: { "line-color": "#7c3aed", "line-width": 2, "line-dasharray": [2, 1] } });
      map.addSource("ov-zoning", { type: "geojson", data: load("zoning") });
      map.addLayer({ id: "ov-zoning", type: "line", source: "ov-zoning", layout: { visibility: "none" },
        paint: { "line-color": "#475569", "line-width": 1.5 } });
      map.addLayer({ id: "ov-zoning-label", type: "symbol", source: "ov-zoning",
        layout: { visibility: "none", "text-field": ["get", "zone"], "text-size": 12, "text-font": ["Noto Sans Bold"] },
        paint: { "text-color": "#1e293b", "text-halo-color": "#ffffff", "text-halo-width": 1.5 } });

      map.addLayer({ id: "sites-selected", type: "line", source: "sites",
        filter: ["==", ["get", "site_id"], ""], paint: { "line-color": "#111827", "line-width": 3 } });

      map.on("click", "sites-fill", (e) => onSelectRef.current(String(e.features?.[0]?.properties?.site_id ?? "")));
      map.on("mousemove", "sites-fill", (e) => {
        map.getCanvas().style.cursor = "pointer";
        const p = e.features?.[0]?.properties;
        if (p) setHover({ x: e.point.x, y: e.point.y,
          text: `${p.location ?? `Block ${p.block} Lot ${p.lot}`} · ${p.status === "scored" ? `score ${p.score}` : "not scored"}` });
      });
      map.on("mouseleave", "sites-fill", () => { map.getCanvas().style.cursor = ""; setHover(null); });
      setReady(true);
    });
    return () => map.remove();
  }, []);

  // Push filtered sites (light properties only) into the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const light = features.map((f) => ({
      type: "Feature" as const, geometry: f.geometry,
      properties: { site_id: f.properties.site_id, score: f.properties.score ?? 0, status: f.properties.status,
        location: f.properties.location, block: f.properties.block, lot: f.properties.lot },
    }));
    (map.getSource("sites") as GeoJSONSource).setData({ type: "FeatureCollection", features: light });
    if (!fitted.current && light.length) {
      fitted.current = true;
      const b = new maplibregl.LngLatBounds();
      for (const f of light) walk(f.geometry, (c) => b.extend(c as [number, number]));
      map.fitBounds(b, { padding: 20, duration: 0 });
    }
  }, [features, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setFilter("sites-selected", ["==", ["get", "site_id"], selectedId ?? ""]);
    if (selectedId) {
      const f = features.find((x) => x.properties.site_id === selectedId);
      if (f) {
        const b = new maplibregl.LngLatBounds();
        walk(f.geometry, (c) => b.extend(c as [number, number]));
        if (!map.getBounds().contains(b.getCenter())) map.easeTo({ center: b.getCenter(), duration: 400 });
      }
    }
  }, [selectedId, ready, features]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    for (const o of OVERLAYS) {
      const v = overlays[o.key] ? "visible" : "none";
      map.setLayoutProperty(`ov-${o.key}`, "visibility", v);
      if (o.key === "zoning") map.setLayoutProperty("ov-zoning-label", "visibility", v);
    }
  }, [overlays, ready]);

  return (
    <div className="relative h-full w-full">
      <div ref={box} className="h-full w-full" />
      {hover && (
        <div className="pointer-events-none absolute z-10 rounded bg-slate-900/90 px-2 py-1 text-xs text-white"
             style={{ left: hover.x + 12, top: hover.y + 12 }}>{hover.text}</div>
      )}
      <Legend />
    </div>
  );
}

function Legend() {
  const labels = ["0", "10", "25", "40", "60", "75+"];
  return (
    <div className="absolute bottom-6 left-2 z-10 rounded-md border bg-white/95 p-2 text-[11px] shadow-sm">
      <div className="mb-1 font-medium text-slate-700">Upside score</div>
      <div className="flex gap-1">
        {SCORE_STOPS.map(([, c], i) => (
          <div key={i} className="text-center"><div className="h-2.5 w-7 rounded-sm" style={{ background: c }} />{labels[i]}</div>
        ))}
      </div>
      <div className="mt-1 flex gap-3 text-slate-600">
        <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-[#e9d5ff]" />condo</span>
        <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-[#d4d4d8]" />rules not loaded</span>
      </div>
    </div>
  );
}

function walk(g: GeoJSON.Geometry, fn: (c: number[]) => void) {
  const rec = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === "number") fn(c as number[]);
    else if (Array.isArray(c)) c.forEach(rec);
  };
  if ("coordinates" in g) rec(g.coordinates);
}
