import type { TransactionsOverview } from "./transaction-types";

const demoCategories = [
  { id: "1", name: "Groceries" },
  { id: "2", name: "Dining out" },
  { id: "3", name: "Transport" },
  { id: "4", name: "Home" },
  { id: "5", name: "Utilities" },
  { id: "6", name: "Health" },
  { id: "7", name: "Travel" },
  { id: "8", name: "Subscriptions" },
];

const demoKnownTags = ["recurring", "work", "one-off", "shared", "gift"];

const demoTransactions = [
  {
    transactionId: "d-101",
    splitId: "d-101-0",
    description: "Trader Joe's #412",
    amount: 64.32,
    date: "2026-07-18",
    sourceName: "Checking",
    destinationName: "Trader Joe's",
  },
  {
    transactionId: "d-102",
    splitId: "d-102-0",
    description: "Uber *Trip",
    amount: 18.5,
    date: "2026-07-17",
    sourceName: "Checking",
    destinationName: "Uber",
  },
  {
    transactionId: "d-103",
    splitId: "d-103-0",
    description: "Netflix.com",
    amount: 15.49,
    date: "2026-07-16",
    sourceName: "Credit Card",
    destinationName: "Netflix",
  },
  {
    transactionId: "d-104",
    splitId: "d-104-0",
    description: "Blue Bottle Coffee",
    amount: 6.75,
    date: "2026-07-16",
    sourceName: "Credit Card",
    destinationName: "Blue Bottle Coffee",
  },
  {
    transactionId: "d-105",
    splitId: "d-105-0",
    description: "City Water & Power",
    amount: 92.14,
    date: "2026-07-15",
    sourceName: "Checking",
    destinationName: "City Water & Power",
  },
  {
    transactionId: "d-106",
    splitId: "d-106-0",
    description: "Delta Air Lines",
    amount: 412.0,
    date: "2026-07-14",
    sourceName: "Credit Card",
    destinationName: "Delta Air Lines",
  },
  {
    transactionId: "d-107",
    splitId: "d-107-0",
    description: "CVS Pharmacy",
    amount: 23.9,
    date: "2026-07-13",
    sourceName: "Checking",
    destinationName: "CVS Pharmacy",
  },
  {
    transactionId: "d-108",
    splitId: "d-108-0",
    description: "Shell Gas Station",
    amount: 48.6,
    date: "2026-07-12",
    sourceName: "Credit Card",
    destinationName: "Shell",
  },
  {
    transactionId: "d-109",
    splitId: "d-109-0",
    description: "Whole Foods Market",
    amount: 91.27,
    date: "2026-07-11",
    sourceName: "Checking",
    destinationName: "Whole Foods Market",
  },
  {
    transactionId: "d-110",
    splitId: "d-110-0",
    description: "Spotify AB",
    amount: 11.99,
    date: "2026-07-10",
    sourceName: "Credit Card",
    destinationName: "Spotify",
  },
  {
    transactionId: "d-111",
    splitId: "d-111-0",
    description: "Home Depot",
    amount: 134.85,
    date: "2026-07-09",
    sourceName: "Credit Card",
    destinationName: "Home Depot",
  },
  {
    transactionId: "d-112",
    splitId: "d-112-0",
    description: "AMC Theatres",
    amount: 27.0,
    date: "2026-07-08",
    sourceName: "Credit Card",
    destinationName: "AMC Theatres",
  },
];

export function getDemoTransactionsOverview(): TransactionsOverview {
  return {
    transactions: demoTransactions.map((transaction) => ({
      ...transaction,
      currencyCode: "USD",
      category: null,
      tags: [],
    })),
    categories: demoCategories,
    knownTags: demoKnownTags,
    source: "demo",
  };
}
