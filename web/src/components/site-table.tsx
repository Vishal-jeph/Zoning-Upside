"use client";
import { useEffect, useMemo, useState } from "react";
import {
  type ColumnDef, type SortingState, flexRender, getCoreRowModel, getPaginationRowModel, getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fmtNum, scoreColor, type SiteProps } from "@/lib/sites";

const FLAG_SHORT: Record<string, string> = {
  historic: "Historic", flood: "Flood", redev_area: "Redev area", redev_agreement: "Agreement",
  zoning_in_progress: "Rezoning", irregular_lot: "Irregular", exempt: "Exempt", below_min_lot: "Small lot",
  nonconforming: "Nonconforming", area_mismatch: "Area?", zone_split: "Split zone", zone_mismatch: "Zone?",
  subdistrict: "Sub-district",
};

const num = (k: keyof SiteProps, header: string, d = 0): ColumnDef<SiteProps> => ({
  accessorKey: k, header, sortUndefined: "last",
  cell: (c) => <span className="tabular-nums">{fmtNum(c.getValue() as number | null, d)}</span>,
  meta: { right: true },
});

const columns: ColumnDef<SiteProps>[] = [
  {
    accessorKey: "score", header: "Score", sortUndefined: "last", meta: { right: true },
    cell: (c) => {
      const s = c.getValue() as number | null;
      return s == null ? <span className="text-slate-400">—</span> : (
        <span className="inline-block min-w-8 rounded px-1.5 py-0.5 text-center text-xs font-semibold tabular-nums"
              style={{ background: scoreColor(s), color: s >= 40 ? "white" : "#0f172a" }}>{s}</span>);
    },
  },
  { accessorKey: "location", header: "Location", cell: (c) => <span className="font-medium">{(c.getValue() as string) ?? "—"}</span> },
  { id: "blocklot", header: "Block / Lot", accessorFn: (p) => `${p.block}/${p.lot}`, enableSorting: false },
  { accessorKey: "zone_key", header: "Zone" },
  num("existing_stories", "Floors now", 1),
  num("allowed_stories", "Floors allowed", 1),
  num("existing_units", "Units now"),
  num("allowed_units", "Units allowed"),
  num("unused_units", "Unused units"),
  num("lot_area", "Lot sq ft"),
  {
    id: "flags", header: "Flags", enableSorting: false,
    cell: (c) => (
      <div className="flex flex-wrap gap-1">
        {c.row.original.flags.filter((f) => FLAG_SHORT[f.code]).slice(0, 4).map((f) => (
          <span key={f.code} className="rounded bg-slate-100 px-1 text-[10px] text-slate-600">{FLAG_SHORT[f.code]}</span>
        ))}
      </div>
    ),
  },
];

export default function SiteTable({ rows, selectedId, onSelect }: {
  rows: SiteProps[]; selectedId: string | null; onSelect: (id: string) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "score", desc: true }]);
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 50 });
  const data = useMemo(() => rows, [rows]);
  const table = useReactTable({
    data, columns, state: { sorting, pagination }, onSortingChange: setSorting, onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(), getRowId: (r) => r.site_id, autoResetPageIndex: true,
  });

  // When a site is picked on the map, jump to its page.
  useEffect(() => {
    if (!selectedId) return;
    const idx = table.getSortedRowModel().rows.findIndex((r) => r.id === selectedId);
    if (idx >= 0) setPagination((p) => ({ ...p, pageIndex: Math.floor(idx / p.pageSize) }));
  }, [selectedId, table]);

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 text-xs text-slate-600">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const right = (h.column.columnDef.meta as { right?: boolean } | undefined)?.right;
                  const dir = h.column.getIsSorted();
                  return (
                    <th key={h.id} className={`whitespace-nowrap border-b px-2 py-1.5 font-medium ${right ? "text-right" : "text-left"}`}>
                      <button disabled={!h.column.getCanSort()} onClick={h.column.getToggleSortingHandler()}
                              className="inline-flex items-center gap-0.5 disabled:cursor-default">
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {dir === "asc" && <ArrowUp className="h-3 w-3" />}
                        {dir === "desc" && <ArrowDown className="h-3 w-3" />}
                      </button>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id} onClick={() => onSelect(r.id)}
                  className={`cursor-pointer border-b hover:bg-sky-50 ${r.id === selectedId ? "bg-sky-100" : ""}`}>
                {r.getVisibleCells().map((c) => {
                  const right = (c.column.columnDef.meta as { right?: boolean } | undefined)?.right;
                  return <td key={c.id} className={`whitespace-nowrap px-2 py-1 ${right ? "text-right" : ""}`}>
                    {flexRender(c.column.columnDef.cell, c.getContext())}</td>;
                })}
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={columns.length} className="p-6 text-center text-slate-500">No sites match these filters.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-end gap-2 border-t px-2 py-1 text-xs text-slate-600">
        Page {table.getState().pagination.pageIndex + 1} of {Math.max(1, table.getPageCount())}
        <Button variant="outline" size="icon" className="h-6 w-6" disabled={!table.getCanPreviousPage()}
                onClick={() => table.previousPage()}><ChevronLeft className="h-3 w-3" /></Button>
        <Button variant="outline" size="icon" className="h-6 w-6" disabled={!table.getCanNextPage()}
                onClick={() => table.nextPage()}><ChevronRight className="h-3 w-3" /></Button>
      </div>
    </div>
  );
}
