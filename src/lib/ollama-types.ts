export type AnalysisFocus = "overview" | "budget" | "savings";

export type AnalysisSeverity = "info" | "warning" | "opportunity";

export type AnalysisConfidence = "low" | "medium" | "high";

export type AnalysisEffort = "low" | "medium" | "high";

export type EconomyObservation = {
  title: string;
  detail: string;
  severity: AnalysisSeverity;
};

export type BudgetProposal = {
  kind: "adjustment" | "new_category";
  budgetId: string | null;
  category: string;
  currencyCode: string;
  currentPlanned: number;
  suggestedPlanned: number;
  reason: string;
  confidence: AnalysisConfidence;
};

export type SavingsSuggestion = {
  title: string;
  description: string;
  category: string;
  currencyCode: string;
  monthlySaving: number;
  effort: AnalysisEffort;
};

export type EconomyAnalysis = {
  summary: string;
  observations: EconomyObservation[];
  budgetProposals: BudgetProposal[];
  savingsSuggestions: SavingsSuggestion[];
  caveats: string[];
};

export type OllamaAnalysisResponse = {
  model: string;
  generatedAt: string;
  analysis: EconomyAnalysis;
};

export type OllamaStatus = {
  available: boolean;
  model: string;
  modelInstalled: boolean;
  installedModels: string[];
  message?: string;
};
