"use client";

import { useCallback, useState } from "react";
import { CircleDot } from "lucide-react";
import { AppNav } from "@/components/app-nav";
import { formatCurrency } from "@/lib/budget-math";
import type { TransactionSuggestion } from "@/lib/ollama-types";
import type { TransactionsOverview } from "@/lib/transaction-types";
import { TransactionTaggingPanel } from "./transaction-tagging-panel";

async function applySuggestion(suggestion: TransactionSuggestion) {
  await fetch("/api/transactions/apply", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transactionId: suggestion.transactionId,
      splitId: suggestion.splitId,
      categoryName: suggestion.suggestedCategory,
      tags: suggestion.suggestedTags,
    }),
  });
}

export function TransactionsWorkspace({ initialOverview }: { initialOverview: TransactionsOverview }) {
  const [overview, setOverview] = useState(initialOverview);
  const [lastSaved, setLastSaved] = useState("Ready");

  const onApply = useCallback((suggestion: TransactionSuggestion) => {
    setLastSaved("Saving");
    applySuggestion(suggestion)
      .then(() => {
        setOverview((current) => ({
          ...current,
          transactions: current.transactions.filter(
            (item) => !(item.transactionId === suggestion.transactionId && item.splitId === suggestion.splitId),
          ),
        }));
        setLastSaved("Saved");
      })
      .catch(() => setLastSaved("Save failed"));
  }, []);

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
              Transaction tagging
            </h1>
          </div>
          <AppNav />
        </header>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
          <span>
            Source:{" "}
            <span className="font-semibold text-slate-700">
              {overview.source === "firefly" ? "Firefly III API" : "Demo data"}
            </span>
          </span>
          <span className="font-medium text-slate-600">{lastSaved}</span>
        </div>

        <TransactionTaggingPanel transactions={overview.transactions} onApply={onApply} />

        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Needs review</h2>
            <p className="mt-1 text-sm text-slate-500">
              Transactions missing a category or tags. Apply a suggestion above to remove one from this list.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Description</th>
                  <th className="px-3 py-2">From → To</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {overview.transactions.map((transaction) => (
                  <tr
                    key={`${transaction.transactionId}-${transaction.splitId}`}
                    className="border-t border-slate-100"
                  >
                    <td className="px-3 py-3 text-slate-600">{transaction.date}</td>
                    <td className="px-3 py-3 font-medium text-slate-900">{transaction.description}</td>
                    <td className="px-3 py-3 text-slate-600">
                      {transaction.sourceName} → {transaction.destinationName}
                    </td>
                    <td className="px-3 py-3 text-right font-semibold text-slate-900">
                      {formatCurrency(transaction.amount, transaction.currencyCode)}
                    </td>
                  </tr>
                ))}
                {overview.transactions.length === 0 ? (
                  <tr>
                    <td className="px-3 py-6 text-center text-slate-500" colSpan={4}>
                      Nothing to review.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}
