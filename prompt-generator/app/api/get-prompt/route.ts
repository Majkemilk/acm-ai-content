import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import OpenAI from "openai";
import { getMetaPromptForLevel } from "@/lib/metaPrompt";

const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

const LEVEL_INSTRUCTIONS: Record<string, string> = {
  standard:
    "Keep it concise and simple. Your output must be a single prompt that explicitly contains: a ROLE sentence, OBJECTIVE, CONTEXT, TASK, an instruction to state uncertainty when unverifiable, and permission or 1–3 clarification questions. Include a short uncertainty-rules line if the topic involves facts or estimates. Do not guess; if a claim needs external verification, add a short uncertainty note.",
  advanced:
    "Provide a balanced, moderately detailed prompt. Use exactly five section labels (plain text, no bold): ROLE:, OBJECTIVE:, CONTEXT/INPUT:, TASK:, OUTPUT FORMAT:. After OUTPUT FORMAT, write all other requirements (truth-first, clarification, reflection, sources, edge cases, verification reminder, uncertainty rules, permission/questions, optional tools) as continuous prose in varied order, with no further section labels—no Truth-first:, Clarification:, etc. Apply basic Zero-Lie rules; never guess; if unverifiable, explicitly state uncertainty.",
  expert:
    "Apply the expert meta-prompt. Use exactly five section labels (plain text, no bold): ROLE:, OBJECTIVE:, CONTEXT/INPUT:, TASK:, OUTPUT FORMAT:. After OUTPUT FORMAT, write all other requirements (truth-first, clarification, reflection, sources, workflow, chain-of-verification, edge cases, verification reminder, uncertainty rules, permission/questions, self-check, final reminder) as continuous prose in varied order, with no further section labels—no Truth-first:, Clarification:, SELF-CHECK:, etc. Output only PROMPT #2 — no commentary. Never guess; use full ZERO-LIE and HIGH-RISK rules.",
};

function buildUserMessage(metadata: Record<string, string>): string {
  const level = (metadata.level || "standard").toLowerCase();
  const instruction = LEVEL_INSTRUCTIONS[level] ?? LEVEL_INSTRUCTIONS.standard;

  const parts: string[] = [
    "Generate a single prompt from the following form data.",
    "",
    `Level: ${metadata.level ?? "standard"}`,
    `Topic: ${metadata.topic ?? ""}`,
    `Main objective: ${metadata.objective ?? ""}`,
    `Context: ${metadata.context ?? ""}`,
  ];
  if (metadata.audience?.trim()) {
    parts.push(`Target audience: ${metadata.audience}`);
  }
  if (metadata.constraints?.trim()) {
    parts.push(`Constraints: ${metadata.constraints}`);
  }
  if (metadata.format?.trim()) {
    parts.push(`Preferred output format: ${metadata.format}`);
  }
  if (metadata.supportingData?.trim()) {
    parts.push(`Supporting data (use or refer to): ${metadata.supportingData}`);
  }
  if (metadata.factsToAdhereTo?.trim()) {
    parts.push(`Facts to strictly adhere to / do not invent: ${metadata.factsToAdhereTo}`);
  }
  parts.push("");
  parts.push(`Level instruction (follow this): ${instruction}`);
  parts.push("");
  parts.push("Output only the generated prompt, nothing else.");
  parts.push("The generated prompt must explicitly contain each required element for this level (as visible text in the prompt).");

  return parts.join("\n");
}

export async function GET(request: NextRequest) {
  const sessionId = request.nextUrl.searchParams.get("session_id");
  if (!sessionId?.trim()) {
    return NextResponse.json(
      { error: "Missing session_id." },
      { status: 400 }
    );
  }

  if (!STRIPE_SECRET_KEY?.trim()) {
    return NextResponse.json(
      { error: "Stripe is not configured." },
      { status: 500 }
    );
  }
  if (!OPENAI_API_KEY?.trim()) {
    return NextResponse.json(
      { error: "OpenAI is not configured." },
      { status: 500 }
    );
  }

  const stripe = new Stripe(STRIPE_SECRET_KEY);

  let session: Stripe.Checkout.Session;
  try {
    session = await stripe.checkout.sessions.retrieve(sessionId.trim(), {
      expand: [],
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Stripe error.";
    return NextResponse.json(
      { error: `Invalid or expired session: ${message}` },
      { status: 400 }
    );
  }

  if (session.payment_status !== "paid") {
    return NextResponse.json(
      { error: "Payment not completed for this session." },
      { status: 400 }
    );
  }

  const metadata = (session.metadata ?? {}) as Record<string, string>;
  if (!metadata.topic?.trim() || !metadata.objective?.trim() || !metadata.context?.trim()) {
    return NextResponse.json(
      { error: "Session metadata is incomplete (missing topic, objective, or context)." },
      { status: 400 }
    );
  }

  const level = (metadata.level ?? "standard").toLowerCase();
  let systemPrompt: string;
  if (level === "standard" || level === "advanced" || level === "expert") {
    systemPrompt = getMetaPromptForLevel(level);
  } else {
    return NextResponse.json(
      { error: "Invalid level in session metadata." },
      { status: 400 }
    );
  }

  const model =
    level === "expert"
      ? "gpt-4o"
      : "gpt-4o-mini";

  const userContent = buildUserMessage(metadata);

  const openai = new OpenAI({ apiKey: OPENAI_API_KEY });

  try {
    const completion = await openai.chat.completions.create({
      model,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userContent },
      ],
      temperature: 0.4,
    });

    const promptText =
      completion.choices?.[0]?.message?.content?.trim() ?? "";
    if (!promptText) {
      return NextResponse.json(
        { error: "OpenAI returned an empty prompt." },
        { status: 500 }
      );
    }

    return NextResponse.json({ prompt: promptText });
  } catch (err) {
    const message = err instanceof Error ? err.message : "OpenAI error.";
    return NextResponse.json(
      { error: `Failed to generate prompt: ${message}` },
      { status: 500 }
    );
  }
}
