"use client";

import { useState } from "react";
import { CircleAlert, LoaderCircle, Sparkles, Tags } from "lucide-react";
import { confirmTransactionApply } from "@/lib/confirm-budget-action";
import type { TransactionCategorizationResponse, TransactionSuggestion } from "@/lib/ollama-types";
import type { TransactionSplit } from "@/lib/transaction-types";

async function readError(response: Response) {
  try {
    const body = (await response.json()) as { error?: string };
    return body.error || "The categorization failed.";
  } catch {
    return "The categorization failed.";
  }
}

export function TransactionTaggingPanel({
  transactions,
  onApply,
}: {
  transactions: TransactionSplit[];
  onApply: (suggestion: TransactionSuggestion) => void;
}) {
  const [result, setResult] = useState<TransactionCategorizationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [appliedKeys, setAppliedKeys] = useState<string[]>([]);

  const runCategorization = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/transactions/categorize", { method: "POST" });

      if (!response.ok) {
        throw new Error(await readError(response));
      }

      setResult((await response.json()) as TransactionCategorizationResponse);
    } catch (categorizationError) {
      setError(
        categorizationError instanceof Error ? categorizationError.message : "The categorization failed.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const applySuggestion = (suggestion: TransactionSuggestion) => {
    const transaction = transactions.find(
      (item) => item.transactionId === suggestion.transactionId && item.splitId === suggestion.splitId,
    );
    const approved = confirmTransactionApply(
      `Apply Ollama suggestion for ${transaction?.description ?? "this transaction"}?`,
      `Set category to "${suggestion.suggestedCategory}" with tags: ${suggestion.suggestedTags.join(", ") || "none"}.`,
    );

    if (!approved) {
      return;
    }

    onApply(suggestion);
    setAppliedKeys((current) => [...current, `${suggestion.transactionId}-${suggestion.splitId}`]);
  };

  return (
    <section className="overflow-hidden rounded-lg border border-violet-200 bg-white shadow-sm">
      <div className="flex flex-col gap-4 border-b border-violet-100 bg-violet-50/60 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-violet-600 text-white shadow-sm">
            <Tags className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-slate-950">Transaction tagging assistant</h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-600">
              Ollama suggests a category and tags for transactions that are missing them. Suggestions stay
              as drafts until you review and apply them.
            </p>
          </div>
        </div>
        <button
          type="button"
          className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md bg-violet-600 px-4 text-sm font-semibold text-white shadow-sm hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={() => void runCategorization()}
          disabled={isLoading || transactions.length === 0}
        >
          {isLoading ? (
            <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles className="size-4" aria-hidden="true" />
          )}
          {isLoading ? "Analyzing locally…" : "Suggest categories & tags"}
        </button>
      </div>

      <div className="p-4">
        {transactions.length === 0 ? (
          <p className="text-sm text-slate-500">Every recent transaction already has a category and tags.</p>
        ) : null}

        {error ? (
          <div
            className="mt-4 flex gap-2 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800"
            role="alert"
          >
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}

        {result && result.suggestions.length > 0 ? (
          <div className="mt-4 overflow-x-auto rounded-md border border-slate-200">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Transaction</th>
                  <th className="px-3 py-2">Suggested category</th>
                  <th className="px-3 py-2">Suggested tags</th>
                  <th className="px-3 py-2">Reason</th>
                  <th className="px-3 py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {result.suggestions.map((suggestion) => {
                  const key = `${suggestion.transactionId}-${suggestion.splitId}`;
                  const transaction = transactions.find(
                    (item) =>
                      item.transactionId === suggestion.transactionId && item.splitId === suggestion.splitId,
                  );
                  const wasApplied = appliedKeys.includes(key);

                  return (
                    <tr key={key} className="border-t border-slate-100 align-top">
                      <td className="px-3 py-3">
                        <p className="font-semibold text-slate-900">
                          {transaction?.description ?? "Unknown transaction"}
                        </p>
                        <p className="mt-0.5 text-xs capitalize text-slate-500">
                          {suggestion.confidence} confidence
                        </p>
                      </td>
                      <td className="px-3 py-3 font-semibold text-violet-700">{suggestion.suggestedCategory}</td>
                      <td className="px-3 py-3 text-slate-600">{suggestion.suggestedTags.join(", ") || "—"}</td>
                      <td className="max-w-xl px-3 py-3 leading-5 text-slate-600">{suggestion.reason}</td>
                      <td className="px-3 py-3 text-right">
                        <button
                          type="button"
                          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-default disabled:text-emerald-700"
                          onClick={() => applySuggestion(suggestion)}
                          disabled={wasApplied}
                        >
                          {wasApplied ? "Applied" : "Review & apply"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}
