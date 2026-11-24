"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Map" },
  { href: "/zones", label: "Zone rules" },
  { href: "/about", label: "About" },
];

export default function SiteHeader() {
  const path = usePathname();
  return (
    <header className="flex h-12 shrink-0 items-center gap-6 border-b bg-white px-4">
      <Link href="/" className="flex items-baseline gap-2">
        <span className="font-semibold tracking-tight">Zoning Upside</span>
        <span className="text-xs text-slate-500">Hoboken, NJ</span>
      </Link>
      <nav className="flex gap-1 text-sm">
        {NAV.map((n) => (
          <Link key={n.href} href={n.href}
                className={`rounded px-2.5 py-1 ${path === n.href ? "bg-slate-100 font-medium" : "text-slate-600 hover:bg-slate-50"}`}>
            {n.label}
          </Link>
        ))}
      </nav>
      <span className="ml-auto hidden text-xs text-slate-500 md:block">
        Estimate based on public zoning text; verify with the Hoboken Zoning Office.
      </span>
    </header>
  );
}
