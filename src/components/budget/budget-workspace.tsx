"use client";

import { useCallback, useMemo, useState, useTransition } from "react";
import { CalendarDays, CircleDot, Redo2, RefreshCcw, Undo2 } from "lucide-react";
import type { BudgetOverview } from "@/lib/budget-types";
import { cloneOverview } from "@/lib/budget-math";
import type { BudgetProposal } from "@/lib/ollama-types";
import { BudgetModeSwitcher, type BudgetMode } from "./budget-mode-switcher";
import { MonthlyFollowUpTable } from "./monthly-follow-up-table";
import { OllamaAssistant } from "./ollama-assistant";
import { BudgetSummaryCards } from "./summary-cards";
import { YearPlanningTable } from "./year-planning-table";

async function persistLimit(input: {
  budgetId: string;
  limitId?: string;
  amount: number;
  start: string;
  end: string;
}) {
  await fetch("/api/budgets/limits", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

function getPlannedAmount(overview: BudgetOverview, budgetId: string, monthKey: string) {
  return overview.budgets.find((budget) => budget.id === budgetId)?.cells[monthKey]?.planned ?? 0;
}

function haveSamePlannedAmounts(left: BudgetOverview, right: BudgetOverview) {
  return left.budgets.every((leftBudget) => {
    const rightBudget = right.budgets.find((budget) => budget.id === leftBudget.id);

    if (!rightBudget) {
      return false;
    }

    return left.months.every((month) => {
      const leftAmount = leftBudget.cells[month.key]?.planned ?? 0;
      const rightAmount = rightBudget.cells[month.key]?.planned ?? 0;

      return leftAmount === rightAmount;
    });
  });
}

function addUndoSnapshot(history: { past: BudgetOverview[]; future: BudgetOverview[] }, snapshot: BudgetOverview) {
  const latest = history.past.at(-1);

  if (latest && haveSamePlannedAmounts(latest, snapshot)) {
    return {
      past: history.past,
      future: [],
    };
  }

  return {
    past: [...history.past.slice(-9), cloneOverview(snapshot)],
    future: [],
  };
}

export function BudgetCockpitPage({ initialOverview }: { initialOverview: BudgetOverview }) {
  const [overview, setOverview] = useState(initialOverview);
  const [history, setHistory] = useState<{
    past: BudgetOverview[];
    future: BudgetOverview[];
  }>({ past: [], future: [] });
  const [activeMonthKey, setActiveMonthKey] = useState(initialOverview.activeMonthKey);
  const [mode, setMode] = useState<BudgetMode>("follow-up");
  const [lastSaved, setLastSaved] = useState("Ready");
  const [isPending, startTransition] = useTransition();
  const currency = overview.budgets[0]?.currencyCode ?? "USD";
  const activeMonth = overview.months.find((month) => month.key === activeMonthKey) ?? overview.months[0];
  const activeMonthIndex = Math.max(
    0,
    overview.months.findIndex((month) => month.key === activeMonthKey),
  );
  const yearOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const years = Array.from({ length: 9 }, (_, index) => currentYear - 4 + index);

    return [...new Set([...years, overview.year])].sort((a, b) => a - b);
  }, [overview.year]);

  const persistOverviewDiff = useCallback(async (from: BudgetOverview, to: BudgetOverview) => {
    const updates = to.budgets.flatMap((budget) =>
      to.months.flatMap((month) => {
        const nextCell = budget.cells[month.key];
        const previousAmount = getPlannedAmount(from, budget.id, month.key);
        const nextAmount = nextCell?.planned ?? 0;

        if (previousAmount === nextAmount) {
          return [];
        }

        return [
          persistLimit({
            budgetId: budget.id,
            limitId: nextCell?.limitId,
            amount: nextAmount,
            start: month.start,
            end: month.end,
          }),
        ];
      }),
    );

    await Promise.all(updates);
  }, []);

  const commitOverview = useCallback((next: BudgetOverview, status = "Saving") => {
    setHistory((current) => addUndoSnapshot(current, overview));
    setOverview(next);
    setLastSaved(status);
  }, [overview]);

  const restoreOverview = useCallback((target: BudgetOverview, direction: "undo" | "redo") => {
    const currentSnapshot = cloneOverview(overview);
    const targetSnapshot = cloneOverview(target);

    setHistory((current) => {
      if (direction === "undo") {
        return {
          past: current.past.slice(0, -1),
          future: [currentSnapshot, ...current.future].slice(0, 10),
        };
      }

      return {
        past: [...current.past.slice(-9), currentSnapshot],
        future: current.future.slice(1),
      };
    });

    setOverview(targetSnapshot);
    setActiveMonthKey(targetSnapshot.months[activeMonthIndex]?.key ?? targetSnapshot.activeMonthKey);
    setLastSaved(direction === "undo" ? "Undoing" : "Redoing");
    startTransition(async () => {
      try {
        await persistOverviewDiff(currentSnapshot, targetSnapshot);
        setLastSaved(direction === "undo" ? "Undone" : "Redone");
      } catch {
        setLastSaved(direction === "undo" ? "Undo failed" : "Redo failed");
      }
    });
  }, [activeMonthIndex, overview, persistOverviewDiff]);

  const undo = useCallback(() => {
    const target = history.past.at(-1);

    if (target) {
      restoreOverview(target, "undo");
    }
  }, [history.past, restoreOverview]);

  const redo = useCallback(() => {
    const target = history.future[0];

    if (target) {
      restoreOverview(target, "redo");
    }
  }, [history.future, restoreOverview]);

  const loadOverview = useCallback((year: number, preferredMonthIndex = activeMonthIndex, successStatus = "Ready") => {
    setLastSaved("Loading");
    startTransition(async () => {
      try {
        const response = await fetch(`/api/budgets/overview?year=${year}`);

        if (!response.ok) {
          throw new Error("Unable to load budget overview");
        }

        const next = (await response.json()) as BudgetOverview;
        setOverview(next);
        setHistory({ past: [], future: [] });
        setActiveMonthKey(next.months[preferredMonthIndex]?.key ?? next.activeMonthKey);
        setLastSaved(successStatus);
      } catch {
        setLastSaved("Load failed");
      }
    });
  }, [activeMonthIndex]);

  const saveCell = useCallback(
    (budgetId: string, monthKey: string, amount: number) => {
      const budget = overview.budgets.find((item) => item.id === budgetId);
      const month = overview.months.find((item) => item.key === monthKey);
      const cell = budget?.cells[monthKey];

      if (!budget || !month) {
        return;
      }

      setLastSaved("Saving");
      startTransition(async () => {
        try {
          await persistLimit({
            budgetId,
            limitId: cell?.limitId,
            amount,
            start: month.start,
            end: month.end,
          });
          setLastSaved("Saved");
        } catch {
          setLastSaved("Save failed");
        }
      });
    },
    [overview.budgets, overview.months],
  );

  const changePlan = useCallback(
    (budgetId: string, monthKey: string, value: number) => {
      setOverview((current) => {
        const next = cloneOverview(current);
        const budget = next.budgets.find((item) => item.id === budgetId);

        if (budget) {
          budget.cells[monthKey] = {
            actual: budget.cells[monthKey]?.actual ?? 0,
            limitId: budget.cells[monthKey]?.limitId,
            planned: Math.max(0, value),
          };
        }

        return next;
      });
      setHistory((current) => addUndoSnapshot(current, overview));
      saveCell(budgetId, monthKey, Math.max(0, value));
    },
    [overview, saveCell],
  );

  const quickAdjust = useCallback(
    (budgetId: string, monthKey: string, delta: number) => {
      const budget = overview.budgets.find((item) => item.id === budgetId);
      const currentValue = budget?.cells[monthKey]?.planned ?? 0;
      changePlan(budgetId, monthKey, currentValue + delta);
    },
    [changePlan, overview.budgets],
  );

  const copyPreviousMonth = useCallback(
    (monthKey: string) => {
      const monthIndex = overview.months.findIndex((month) => month.key === monthKey);

      if (monthIndex <= 0) {
        return;
      }

      const previousMonthKey = overview.months[monthIndex - 1].key;
      const next = cloneOverview(overview);
      next.budgets.forEach((budget) => {
        const previous = budget.cells[previousMonthKey]?.planned ?? 0;
        budget.cells[monthKey] = {
          actual: budget.cells[monthKey]?.actual ?? 0,
          limitId: budget.cells[monthKey]?.limitId,
          planned: previous,
        };
      });
      commitOverview(next);

      overview.budgets.forEach((budget) => {
        saveCell(budget.id, monthKey, budget.cells[previousMonthKey]?.planned ?? 0);
      });
    },
    [commitOverview, overview, saveCell],
  );

  const copyMonthToRestOfYear = useCallback(
    (monthKey: string) => {
      const monthIndex = overview.months.findIndex((month) => month.key === monthKey);

      if (monthIndex < 0 || monthIndex >= overview.months.length - 1) {
        return;
      }

      const targetMonths = overview.months.slice(monthIndex + 1);
      const next = cloneOverview(overview);
      next.budgets.forEach((budget) => {
        const source = budget.cells[monthKey]?.planned ?? 0;
        targetMonths.forEach((month) => {
          budget.cells[month.key] = {
            actual: budget.cells[month.key]?.actual ?? 0,
            limitId: budget.cells[month.key]?.limitId,
            planned: source,
          };
        });
      });
      commitOverview(next);

      overview.budgets.forEach((budget) => {
        const source = budget.cells[monthKey]?.planned ?? 0;
        targetMonths.forEach((month) => saveCell(budget.id, month.key, source));
      });
    },
    [commitOverview, overview, saveCell],
  );

  const distributeAnnualAmount = useCallback(
    (budgetId: string, amount: number) => {
      const monthlyAmount = Math.max(0, amount) / Math.max(1, overview.months.length);

      const next = cloneOverview(overview);
      const budget = next.budgets.find((item) => item.id === budgetId);

      if (budget) {
        next.months.forEach((month) => {
          budget.cells[month.key] = {
            actual: budget.cells[month.key]?.actual ?? 0,
            limitId: budget.cells[month.key]?.limitId,
            planned: monthlyAmount,
          };
        });
      }

      commitOverview(next);

      overview.months.forEach((month) => saveCell(budgetId, month.key, monthlyAmount));
    },
    [commitOverview, overview, saveCell],
  );

  const copySameMonthLastYear = useCallback(
    (budgetId: string, monthKey: string) => {
      const targetMonth = overview.months.find((month) => month.key === monthKey);

      if (!targetMonth) {
        return;
      }

      setLastSaved("Loading");
      startTransition(async () => {
        try {
          const response = await fetch(`/api/budgets/overview?year=${overview.year - 1}`);

          if (!response.ok) {
            throw new Error("Unable to load previous year");
          }

          const previousOverview = (await response.json()) as BudgetOverview;
          const previousMonthKey = `${overview.year - 1}-${monthKey.slice(5)}`;
          const sourceBudget = previousOverview.budgets.find((budget) => budget.id === budgetId);
          const sourceAmount = sourceBudget?.cells[previousMonthKey]?.planned;

          if (sourceAmount === undefined) {
            setLastSaved("No prior amount");
            return;
          }

          const next = cloneOverview(overview);
          const budget = next.budgets.find((item) => item.id === budgetId);

          if (budget) {
            budget.cells[monthKey] = {
              actual: budget.cells[monthKey]?.actual ?? 0,
              limitId: budget.cells[monthKey]?.limitId,
              planned: sourceAmount,
            };
          }

          commitOverview(next);
          await persistLimit({
            budgetId,
            limitId: overview.budgets.find((budget) => budget.id === budgetId)?.cells[monthKey]?.limitId,
            amount: sourceAmount,
            start: targetMonth.start,
            end: targetMonth.end,
          });
          setLastSaved("Saved");
        } catch {
          setLastSaved("Copy failed");
        }
      });
    },
    [commitOverview, overview],
  );

  const refresh = useCallback(() => {
    loadOverview(overview.year, activeMonthIndex, "Refreshed");
  }, [activeMonthIndex, loadOverview, overview.year]);

  const applyOllamaProposal = useCallback(
    (proposal: BudgetProposal) => {
      if (proposal.budgetId) {
        changePlan(proposal.budgetId, activeMonthKey, proposal.suggestedPlanned);
      }
    },
    [activeMonthKey, changePlan],
  );

  const monthOptions = useMemo(
    () =>
      overview.months.map((month) => (
        <button
          key={month.key}
          type="button"
          className={
            month.key === activeMonthKey
              ? "h-8 shrink-0 rounded-md bg-slate-950 px-3 text-sm font-semibold text-white"
              : "h-8 shrink-0 rounded-md px-3 text-sm font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          }
          onClick={() => setActiveMonthKey(month.key)}
        >
          {month.label}
        </button>
      )),
    [activeMonthKey, overview.months],
  );

  return (
    <main className="min-h-screen bg-[#f7f8fb] text-slate-950">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-3 px-3 py-3 sm:gap-4 sm:px-6 sm:py-4 lg:px-8">
        <header className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white px-3 py-4 shadow-sm sm:px-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-semibold text-sky-700">
              <CircleDot className="size-4 shrink-0" aria-hidden="true" />
              <span className="truncate">Firefly III Assistant</span>
            </div>
            <h1 className="mt-2 text-xl font-semibold tracking-normal text-slate-950 sm:text-2xl">
              Budget cockpit
            </h1>
          </div>

          <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center lg:justify-end">
            <div className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 text-sm font-medium text-slate-600">
              <CalendarDays className="size-4 shrink-0" aria-hidden="true" />
              {activeMonth.label} {overview.year}
            </div>
            <label className="sr-only" htmlFor="budget-year">
              Budget year
            </label>
            <select
              id="budget-year"
              className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 outline-none transition hover:bg-slate-50 focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              value={overview.year}
              onChange={(event) => loadOverview(Number(event.target.value), activeMonthIndex)}
            >
              {yearOptions.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
            <div className="min-w-0 rounded-md border border-slate-200 bg-white p-1">
              <div className="flex max-w-full gap-1 overflow-x-auto overscroll-x-contain pb-1 sm:pb-0">
                {monthOptions}
              </div>
            </div>
            <button
              type="button"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 sm:justify-start"
              onClick={refresh}
            >
              <RefreshCcw className="size-4" aria-hidden="true" />
              Refresh
            </button>
          </div>
        </header>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
          <span>
            Source:{" "}
            <span className="font-semibold text-slate-700">
              {overview.source === "firefly" ? "Firefly III API" : "Demo data"}
            </span>
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={undo}
              disabled={history.past.length === 0 || isPending}
              title="Undo last budget change"
            >
              <Undo2 className="size-4" aria-hidden="true" />
              Undo
            </button>
            <button
              type="button"
              className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={redo}
              disabled={history.future.length === 0 || isPending}
              title="Redo last undone budget change"
            >
              <Redo2 className="size-4" aria-hidden="true" />
              Redo
            </button>
            <span className="font-medium text-slate-600">{isPending ? "Working" : lastSaved}</span>
          </div>
        </div>

        <BudgetSummaryCards budgets={overview.budgets} monthKey={activeMonthKey} currency={currency} />
        <OllamaAssistant
          year={overview.year}
          monthKey={activeMonthKey}
          monthLabel={activeMonth.label}
          onApplyProposal={applyOllamaProposal}
        />
        <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-950">
              {mode === "follow-up" ? "Daily follow-up" : "Annual planning"}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              {mode === "follow-up"
                ? "One selected month, sorted for fast review."
                : "All months are visible for occasional year-level edits."}
            </p>
          </div>
          <BudgetModeSwitcher mode={mode} onModeChange={setMode} />
        </div>

        {mode === "follow-up" ? (
          <MonthlyFollowUpTable
            rows={overview.budgets}
            months={overview.months}
            activeMonthKey={activeMonthKey}
            onPlanChange={changePlan}
            onQuickAdjust={quickAdjust}
          />
        ) : (
          <YearPlanningTable
            rows={overview.budgets}
            months={overview.months}
            year={overview.year}
            activeMonthKey={activeMonthKey}
            onActiveMonthChange={setActiveMonthKey}
            onPlanChange={changePlan}
            onCopyPreviousMonth={copyPreviousMonth}
            onCopyMonthToRestOfYear={copyMonthToRestOfYear}
            onCopySameMonthLastYear={copySameMonthLastYear}
            onDistributeAnnualAmount={distributeAnnualAmount}
          />
        )}
      </div>
    </main>
  );
}

export const BudgetWorkspace = BudgetCockpitPage;
