import type { BudgetMonth, BudgetRow } from "@/lib/budget-types";
import { formatCurrency, summarizeMonth } from "@/lib/budget-math";
import { cn } from "@/lib/utils";

export function MonthComparison({
  rows,
  months,
  activeMonthKey,
  currency,
}: {
  rows: BudgetRow[];
  months: BudgetMonth[];
  activeMonthKey: string;
  currency: string;
}) {
  const activeIndex = months.findIndex((month) => month.key === activeMonthKey);
  const previousMonth = months[Math.max(0, activeIndex - 1)];
  const current = summarizeMonth(rows, activeMonthKey);
  const previous = summarizeMonth(rows, previousMonth.key);
  const delta = current.totalSpending - previous.totalSpending;

  return (
    <section className="grid gap-3 md:grid-cols-[1fr_1fr_1.4fr]">
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-sm font-medium text-slate-500">This month vs {previousMonth.label}</p>
        <p
          className={cn(
            "mt-2 text-xl font-semibold",
            delta <= 0 ? "text-emerald-700" : "text-rose-700",
          )}
        >
          {delta <= 0 ? "-" : "+"}
          {formatCurrency(Math.abs(delta), currency)}
        </p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-sm font-medium text-slate-500">Attention needed</p>
        <p className="mt-2 text-xl font-semibold text-slate-950">
          {current.overspends.length} categories
        </p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-sm font-medium text-slate-500">Monthly run rate</p>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className={cn(
              "h-full rounded-full",
              current.utilization >= 1 ? "bg-rose-500" : current.utilization >= 0.8 ? "bg-amber-400" : "bg-emerald-500",
            )}
            style={{ width: `${Math.min(100, Math.round(current.utilization * 100))}%` }}
          />
        </div>
      </div>
    </section>
  );
}
