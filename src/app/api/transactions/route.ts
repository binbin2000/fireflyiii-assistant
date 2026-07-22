import { NextResponse } from "next/server";
import { getTransactionsNeedingReview } from "@/lib/firefly";

export async function GET() {
  try {
    return NextResponse.json(await getTransactionsNeedingReview());
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unable to load transactions" },
      { status: 500 },
    );
  }
}
