import { BudgetWorkspace } from "@/components/budget/budget-workspace";
import { getBudgetOverview } from "@/lib/firefly";

export const dynamic = "force-dynamic";

export default async function Home() {
  const overview = await getBudgetOverview();

  return <BudgetWorkspace initialOverview={overview} />;
}
