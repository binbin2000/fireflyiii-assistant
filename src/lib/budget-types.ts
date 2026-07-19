export type BudgetHealth = "good" | "warning" | "danger";

export type BudgetMonth = {
  key: string;
  label: string;
  start: string;
  end: string;
};

export type BudgetCell = {
  planned: number;
  actual: number;
  limitId?: string;
};

export type BudgetRow = {
  id: string;
  name: string;
  group: string;
  currencyCode: string;
  currencySymbol: string;
  cells: Record<string, BudgetCell>;
};

export type BudgetOverview = {
  year: number;
  activeMonthKey: string;
  months: BudgetMonth[];
  budgets: BudgetRow[];
  source: "firefly" | "demo";
};

export type BudgetSummary = {
  totalBudget: number;
  totalSpending: number;
  remaining: number;
  utilization: number;
  overspends: Array<{
    id: string;
    name: string;
    amount: number;
  }>;
};
