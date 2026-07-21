import { getTransactionsNeedingReview } from "@/lib/firefly";
import { categorizeTransactions, OllamaIntegrationError } from "@/lib/ollama";

export async function POST() {
  try {
    const overview = await getTransactionsNeedingReview();

    return Response.json(
      await categorizeTransactions({
        transactions: overview.transactions,
        categories: overview.categories,
      }),
    );
  } catch (error) {
    const status = error instanceof OllamaIntegrationError ? error.status : 500;

    return Response.json(
      { error: error instanceof Error ? error.message : "Unable to categorize transactions." },
      { status },
    );
  }
}
