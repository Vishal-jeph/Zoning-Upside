import Link from "next/link";
import { DISCLAIMER } from "@/lib/rules";

// Placeholder until Phase 4 (map, filters, table).
export default function Home() {
  return (
    <main className="mx-auto max-w-2xl space-y-4 p-8">
      <h1 className="text-2xl font-semibold tracking-tight">Zoning Upside: Hoboken</h1>
      <p className="text-slate-600">
        Finds Hoboken properties where zoning appears to allow a bigger building than what stands there today.
      </p>
      <ul className="list-disc pl-5 text-sky-700 underline">
        <li><Link href="/rules/review">Zone rules review (local only)</Link></li>
      </ul>
      <p className="text-xs text-slate-500">{DISCLAIMER}</p>
    </main>
  );
}
