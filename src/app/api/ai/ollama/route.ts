import { getBudgetOverview } from "@/lib/firefly";
import { analyzeEconomy, getOllamaStatus, OllamaIntegrationError } from "@/lib/ollama";
import type { AnalysisFocus } from "@/lib/ollama-types";

const focuses: AnalysisFocus[] = ["overview", "budget", "savings"];

export async function GET() {
  return Response.json(await getOllamaStatus());
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as {
      year?: unknown;
      monthKey?: unknown;
      focus?: unknown;
      question?: unknown;
    };
    const year = typeof body.year === "number" ? body.year : Number.NaN;
    const focus = focuses.includes(body.focus as AnalysisFocus)
      ? (body.focus as AnalysisFocus)
      : "overview";

    if (!Number.isInteger(year) || year < 2000 || year > 2200) {
      return Response.json({ error: "A valid budget year is required." }, { status: 400 });
    }

    const overview = await getBudgetOverview(year);
    const requestedMonthKey = typeof body.monthKey === "string" ? body.monthKey : "";
    const monthKey = overview.months.some((month) => month.key === requestedMonthKey)
      ? requestedMonthKey
      : overview.activeMonthKey;

    return Response.json(
      await analyzeEconomy({
        overview,
        monthKey,
        focus,
        question: typeof body.question === "string" ? body.question : undefined,
      }),
    );
  } catch (error) {
    const status = error instanceof OllamaIntegrationError ? error.status : 500;

    return Response.json(
      { error: error instanceof Error ? error.message : "Unable to analyze the budget." },
      { status },
    );
  }
}
