"use client";

/* eslint-disable react-hooks/incompatible-library */
import { useMemo } from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronsRight, Copy, Wand2 } from "lucide-react";
import type { BudgetMonth, BudgetRow } from "@/lib/budget-types";
import { confirmBudgetOverwrite } from "@/lib/confirm-budget-action";
import { formatCurrency, getHealth, getRemaining, getUtilization } from "@/lib/budget-math";
import { cn } from "@/lib/utils";
import { StatusPill } from "./status-pill";

function BudgetMobileCards({
  rows,
  months,
  activeMonthKey,
  onPlanChange,
  onQuickAdjust,
}: {
  rows: BudgetRow[];
  months: BudgetMonth[];
  activeMonthKey: string;
  onPlanChange: (budgetId: string, monthKey: string, value: number) => void;
  onQuickAdjust: (budgetId: string, monthKey: string, delta: number) => void;
}) {
  const activeMonth = months.find((month) => month.key === activeMonthKey);

  return (
    <div className="space-y-3 p-3 lg:hidden">
      {rows.map((row) => {
        const cell = row.cells[activeMonthKey] ?? { planned: 0, actual: 0 };
        const remaining = getRemaining(cell.planned, cell.actual);
        const utilization = getUtilization(cell.planned, cell.actual);
        const health = getHealth(cell.planned, cell.actual);

        return (
          <article
            key={row.id}
            className={cn(
              "rounded-lg border bg-white p-3 shadow-sm",
              health === "good" && "border-slate-200",
              health === "warning" && "border-amber-200",
              health === "danger" && "border-rose-200",
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-semibold text-slate-950">{row.name}</h3>
                <p className="mt-0.5 truncate text-xs font-medium text-slate-500">
                  {row.group} - {activeMonth?.label}
                </p>
              </div>
              <StatusPill health={health} />
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
              <div className="rounded-md bg-slate-50 p-2">
                <p className="text-xs font-medium text-slate-500">Actual</p>
                <p className="mt-1 font-semibold text-slate-800">
                  {formatCurrency(cell.actual, row.currencyCode)}
                </p>
              </div>
              <div className="rounded-md bg-slate-50 p-2">
                <p className="text-xs font-medium text-slate-500">Left</p>
                <p className={cn("mt-1 font-semibold", remaining < 0 ? "text-rose-700" : "text-emerald-700")}>
                  {formatCurrency(remaining, row.currencyCode)}
                </p>
              </div>
              <div className="rounded-md bg-slate-50 p-2">
                <p className="text-xs font-medium text-slate-500">Used</p>
                <p className="mt-1 font-semibold text-slate-800">{Math.round(utilization * 100)}%</p>
              </div>
            </div>

            <label className="mt-4 block text-xs font-semibold uppercase text-slate-400">
              Planned budget
            </label>
            <input
              aria-label={`${row.name} ${activeMonth?.label} planned budget`}
              className="mt-1 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-base font-semibold text-slate-950 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              inputMode="decimal"
              value={cell.planned}
              onChange={(event) => onPlanChange(row.id, activeMonthKey, Number(event.target.value) || 0)}
            />

            <div className="mt-3 flex items-center gap-2">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={cn(
                    "h-full rounded-full",
                    health === "good" && "bg-emerald-500",
                    health === "warning" && "bg-amber-400",
                    health === "danger" && "bg-rose-500",
                  )}
                  style={{ width: `${Math.min(100, Math.round(utilization * 100))}%` }}
                />
              </div>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2">
              {[-25, 25, 100].map((delta) => (
                <button
                  key={delta}
                  type="button"
                  className="h-9 rounded-md border border-slate-200 px-2 text-sm font-semibold text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                  onClick={() => onQuickAdjust(row.id, activeMonthKey, delta)}
                >
                  {delta > 0 ? "+" : ""}
                  {delta}
                </button>
              ))}
            </div>
          </article>
        );
      })}
    </div>
  );
}

export function BudgetTable({
  rows,
  months,
  activeMonthKey,
  onPlanChange,
  onCopyPreviousMonth,
  onCopyYear,
  onQuickAdjust,
}: {
  rows: BudgetRow[];
  months: BudgetMonth[];
  activeMonthKey: string;
  onPlanChange: (budgetId: string, monthKey: string, value: number) => void;
  onCopyPreviousMonth: (monthKey: string) => void;
  onCopyYear: () => void;
  onQuickAdjust: (budgetId: string, monthKey: string, delta: number) => void;
}) {
  const columns = useMemo<ColumnDef<BudgetRow>[]>(
    () => [
      {
        id: "budget",
        header: "Budget",
        cell: ({ row }) => {
          const cell = row.original.cells[activeMonthKey];
          const health = getHealth(cell?.planned ?? 0, cell?.actual ?? 0);

          return (
            <div className="flex min-h-20 w-56 flex-col justify-center gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-950">{row.original.name}</p>
                <p className="truncate text-xs font-medium text-slate-500">{row.original.group}</p>
              </div>
              <StatusPill health={health} />
            </div>
          );
        },
      },
      ...months.map<ColumnDef<BudgetRow>>((month, monthIndex) => ({
        id: month.key,
        header: () => (
          <div className="flex min-w-44 items-center justify-between gap-2">
            <span>{month.label}</span>
            <button
              type="button"
              className="grid size-7 place-items-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              onClick={() => {
                if (
                  confirmBudgetOverwrite(
                    "Copy previous month into this month?",
                    `Every budget item in ${month.label} will be replaced with the previous month's planned amount.`,
                  )
                ) {
                  onCopyPreviousMonth(month.key);
                }
              }}
              title={`Copy ${months[Math.max(0, monthIndex - 1)].label} into ${month.label}`}
              disabled={monthIndex === 0}
            >
              <ChevronLeft className="size-4" aria-hidden="true" />
              <span className="sr-only">Copy previous month</span>
            </button>
          </div>
        ),
        cell: ({ row }) => {
          const cell = row.original.cells[month.key] ?? { planned: 0, actual: 0 };
          const remaining = getRemaining(cell.planned, cell.actual);
          const utilization = getUtilization(cell.planned, cell.actual);
          const health = getHealth(cell.planned, cell.actual);

          return (
            <div
              className={cn(
                "min-h-32 w-44 border-l border-slate-100 p-3",
                month.key === activeMonthKey && "bg-sky-50/50",
              )}
            >
              <label className="block text-[11px] font-semibold uppercase text-slate-400">
                Planned
              </label>
              <input
                aria-label={`${row.original.name} ${month.label} planned budget`}
                className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm font-semibold text-slate-950 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                inputMode="decimal"
                value={cell.planned}
                onChange={(event) => onPlanChange(row.original.id, month.key, Number(event.target.value) || 0)}
                onKeyDown={(event) => {
                  const target = event.currentTarget;
                  const rowIndex = row.index;
                  const selector = `[data-budget-input="${rowIndex}:${monthIndex}"]`;
                  target.setAttribute("data-last", selector);

                  if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) {
                    return;
                  }

                  event.preventDefault();
                  const nextRow = rowIndex + (event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0);
                  const nextMonth = monthIndex + (event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0);
                  const next = document.querySelector<HTMLInputElement>(
                    `[data-budget-input="${nextRow}:${nextMonth}"]`,
                  );
                  next?.focus();
                  next?.select();
                }}
                data-budget-input={`${row.index}:${monthIndex}`}
              />
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <p className="font-medium text-slate-400">Actual</p>
                  <p className="mt-1 font-semibold text-slate-700">
                    {formatCurrency(cell.actual, row.original.currencyCode)}
                  </p>
                </div>
                <div>
                  <p className="font-medium text-slate-400">Left</p>
                  <p className={cn("mt-1 font-semibold", remaining < 0 ? "text-rose-700" : "text-emerald-700")}>
                    {formatCurrency(remaining, row.original.currencyCode)}
                  </p>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      health === "good" && "bg-emerald-500",
                      health === "warning" && "bg-amber-400",
                      health === "danger" && "bg-rose-500",
                    )}
                    style={{ width: `${Math.min(100, Math.round(utilization * 100))}%` }}
                  />
                </div>
                <span className="w-9 text-right text-xs font-semibold text-slate-500">
                  {Math.round(utilization * 100)}%
                </span>
              </div>
              <div className="mt-3 flex gap-1">
                {[-25, 25, 100].map((delta) => (
                  <button
                    key={delta}
                    type="button"
                    className="h-7 rounded-md border border-slate-200 px-2 text-xs font-semibold text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                    onClick={() => onQuickAdjust(row.original.id, month.key, delta)}
                  >
                    {delta > 0 ? "+" : ""}
                    {delta}
                  </button>
                ))}
              </div>
            </div>
          );
        },
      })),
    ],
    [activeMonthKey, months, onCopyPreviousMonth, onPlanChange, onQuickAdjust],
  );

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-200 px-3 py-3 sm:px-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-slate-950">Budget plan</h2>
          <p className="text-sm text-slate-500">Edit planned amounts, track actuals, and move numbers quickly.</p>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 lg:flex lg:flex-wrap">
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 lg:h-9"
            onClick={() => {
              if (
                confirmBudgetOverwrite(
                  "Copy previous month into selected month?",
                  "Every budget item in the selected month will be replaced with the previous month's planned amount.",
                )
              ) {
                onCopyPreviousMonth(activeMonthKey);
              }
            }}
          >
            <Copy className="size-4" aria-hidden="true" />
            Copy previous month
          </button>
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-slate-950 px-3 text-sm font-semibold text-white hover:bg-slate-800 lg:h-9"
            onClick={() => {
              if (
                confirmBudgetOverwrite(
                  "Copy the year?",
                  "This bulk action can replace planned budget amounts that are already defined.",
                )
              ) {
                onCopyYear();
              }
            }}
          >
            <ChevronsRight className="size-4" aria-hidden="true" />
            Copy year
          </button>
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-sky-200 bg-sky-50 px-3 text-sm font-semibold text-sky-700 hover:bg-sky-100 lg:h-9"
            onClick={() => {
              if (
                confirmBudgetOverwrite(
                  "Add 10 to every budget item in this month?",
                  "Every planned amount in the selected month will be changed.",
                )
              ) {
                rows.forEach((row) => onQuickAdjust(row.id, activeMonthKey, 10));
              }
            }}
          >
            <Wand2 className="size-4" aria-hidden="true" />
            Add 10 to month
          </button>
        </div>
      </div>

      <BudgetMobileCards
        rows={rows}
        months={months}
        activeMonthKey={activeMonthKey}
        onPlanChange={onPlanChange}
        onQuickAdjust={onQuickAdjust}
      />

      <div className="hidden max-h-[68vh] overflow-auto lg:block">
        <table className="w-max min-w-full border-separate border-spacing-0 text-left">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header, index) => (
                  <th
                    key={header.id}
                    className={cn(
                      "sticky top-0 z-20 border-b border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-600",
                      index === 0 && "left-0 z-30 border-r",
                    )}
                  >
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="group">
                {row.getVisibleCells().map((cell, index) => (
                  <td
                    key={cell.id}
                    className={cn(
                      "border-b border-slate-100 align-top",
                      index === 0 && "sticky left-0 z-10 border-r bg-white px-4 group-hover:bg-slate-50",
                    )}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
