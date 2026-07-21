export type TransactionCategory = {
  id: string;
  name: string;
};

export type TransactionSplit = {
  transactionId: string;
  splitId: string;
  description: string;
  amount: number;
  currencyCode: string;
  date: string;
  sourceName: string;
  destinationName: string;
  category: TransactionCategory | null;
  tags: string[];
};

export type TransactionsOverview = {
  transactions: TransactionSplit[];
  categories: TransactionCategory[];
  knownTags: string[];
  source: "firefly" | "demo";
};
