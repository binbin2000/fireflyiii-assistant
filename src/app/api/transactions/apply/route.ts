import { NextResponse } from "next/server";
import { applyTransactionTags } from "@/lib/firefly";

export async function PATCH(request: Request) {
  try {
    const body = (await request.json()) as {
      transactionId: string;
      splitId: string;
      categoryName?: string;
      tags: string[];
    };

    return NextResponse.json(await applyTransactionTags(body));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unable to save transaction" },
      { status: 500 },
    );
  }
}
