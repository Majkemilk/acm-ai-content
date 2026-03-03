import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { formSchema, LEVEL_CENTS, type FormData } from "@/lib/form-schema";
import { getLevelProductName } from "@/lib/levels";

const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY;
const METADATA_VALUE_MAX_LENGTH = 500;
const METADATA_KEY_MAX_LENGTH = 40;

function buildMetadata(body: FormData): Record<string, string> {
  const meta: Record<string, string> = {};
  for (const [key, value] of Object.entries(body)) {
    if (value === undefined || value === null) continue;
    const str =
      typeof value === "string"
        ? value
        : typeof value === "boolean"
          ? String(value)
          : JSON.stringify(value);
    const truncated = str.slice(0, METADATA_VALUE_MAX_LENGTH);
    if (truncated.length > 0) {
      const safeKey = key.slice(0, METADATA_KEY_MAX_LENGTH);
      meta[safeKey] = truncated;
    }
  }
  return meta;
}

export async function POST(request: NextRequest) {
  if (!STRIPE_SECRET_KEY?.trim()) {
    return NextResponse.json(
      { error: "Stripe is not configured (STRIPE_SECRET_KEY missing)." },
      { status: 500 }
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body." },
      { status: 400 }
    );
  }

  const parsed = formSchema.safeParse(body);
  if (!parsed.success) {
    const first = parsed.error.flatten().fieldErrors;
    const message =
      Object.values(first).flat().find(Boolean) ?? "Validation failed.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const data = parsed.data;
  const level = data.level;
  const amountCents = LEVEL_CENTS[level];
  const origin =
    request.headers.get("origin") ||
    request.nextUrl.origin ||
    "http://localhost:3000";

  const stripe = new Stripe(STRIPE_SECRET_KEY);

  try {
    const session = await stripe.checkout.sessions.create({
      payment_method_types: ["card"],
      mode: "payment",
      line_items: [
        {
          quantity: 1,
          price_data: {
            currency: "eur",
            unit_amount: amountCents,
            product_data: {
              name: `Flowtaro Prompt – ${getLevelProductName(level)}`,
              description: (data.topic || "Custom prompt").slice(0, 500),
              metadata: {},
            },
          },
        },
      ],
      success_url: `${origin}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}/`,
      metadata: buildMetadata(data),
    });

    const url =
      session.url ?? (session.id ? `${origin}/success?session_id=${session.id}` : null);
    return NextResponse.json({
      sessionId: session.id,
      url,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Stripe error.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
