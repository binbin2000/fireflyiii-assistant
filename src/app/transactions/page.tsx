import { TransactionsWorkspace } from "@/components/transactions/transactions-workspace";
import { getTransactionsNeedingReview } from "@/lib/firefly";

export const dynamic = "force-dynamic";

export default async function TransactionsPage() {
  const overview = await getTransactionsNeedingReview();

  return <TransactionsWorkspace initialOverview={overview} />;
}
