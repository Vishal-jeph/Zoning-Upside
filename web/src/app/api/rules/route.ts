// Local-only API for the rules review page. Reads/writes ../data/rules/*.json.
// Disabled outside `next dev` so the deployed site can never modify rules.
import { promises as fs } from "fs";
import path from "path";
import { NextResponse } from "next/server";
import type { ApprovedZone, RulesPayload } from "@/lib/rules";

export const dynamic = "force-dynamic";

const RULES_DIR = path.join(process.cwd(), "..", "data", "rules");
const SOURCES_DIR = path.join(process.cwd(), "..", "data", "sources");
const APPROVED = path.join(RULES_DIR, "hoboken_rules.json");

const devOnly = () =>
  process.env.NODE_ENV !== "development"
    ? NextResponse.json({ error: "The rules review API is only available in local development." }, { status: 403 })
    : null;

async function readJson<T>(file: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await fs.readFile(file, "utf8")) as T;
  } catch {
    return fallback;
  }
}

export async function GET() {
  const blocked = devOnly();
  if (blocked) return blocked;
  const payload: RulesPayload = {
    extracted: await readJson(path.join(RULES_DIR, "extracted_rules.json"), null),
    approved: await readJson(APPROVED, { updated_at: "", zones: {} }),
    manifest: await readJson(path.join(SOURCES_DIR, "manifest.json"), []),
  };
  return NextResponse.json(payload);
}

// Body: { action: "approve", zone: ApprovedZone } | { action: "revoke", zone_key: string }
export async function POST(req: Request) {
  const blocked = devOnly();
  if (blocked) return blocked;
  const body = await req.json();
  const approved = await readJson<RulesPayload["approved"]>(APPROVED, { updated_at: "", zones: {} });

  if (body.action === "approve") {
    const zone = body.zone as ApprovedZone;
    // Guard: a non-null value must cite a source quote, or be explicitly confirmed by the reviewer.
    for (const d of zone.districts) {
      for (const [k, v] of Object.entries(d.fields)) {
        if (v.value === null || v.value === "") continue;
        if (v.basis === "extracted" && !v.quote)
          return NextResponse.json({ error: `${zone.zone_key} ${k}: extracted value has no quote` }, { status: 400 });
      }
    }
    approved.zones[zone.zone_key] = { ...zone, approved_by: "manual", approved_at: new Date().toISOString().slice(0, 10) };
  } else if (body.action === "revoke") {
    delete approved.zones[body.zone_key];
  } else {
    return NextResponse.json({ error: "unknown action" }, { status: 400 });
  }
  approved.updated_at = new Date().toISOString();
  await fs.writeFile(APPROVED, JSON.stringify(approved, null, 2) + "\n");
  return NextResponse.json(approved);
}
