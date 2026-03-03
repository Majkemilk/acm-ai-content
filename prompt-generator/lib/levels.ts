/**
 * Single source of truth for prompt levels: standard / advanced / expert.
 * Use for UI labels, Stripe product names, e-mails, and API metadata.
 */

export const LEVELS = ["standard", "advanced", "expert"] as const;
export type Level = (typeof LEVELS)[number];

/** Price in cents for Stripe (standard 50, advanced 100, expert 300). */
export const LEVEL_CENTS: Record<Level, number> = {
  standard: 50,
  advanced: 100,
  expert: 300,
} as const;

/** Short labels for radio buttons and receipts (e.g. "Standard", "Advanced"). */
export const LEVEL_LABELS: Record<Level, string> = {
  standard: "Standard",
  advanced: "Advanced",
  expert: "Expert",
};

/** Display price in EUR for UI (e.g. 0.5, 1.0, 3.0). */
export const LEVEL_PRICES: Record<Level, number> = {
  standard: 0.5,
  advanced: 1.0,
  expert: 3.0,
};

/** Longer descriptions for "What you get" and product descriptions (UI, Stripe, e-mail). */
export const LEVEL_DESCRIPTIONS: Record<Level, string> = {
  standard:
    "Quick, concise prompts for everyday questions. Ideal for students, hobbyists.",
  advanced:
    "Balanced prompts for business, education, and planning. Includes target audience and format selection.",
  expert:
    "In‑depth prompts with strict fact‑checking for legal, financial, and medical topics. Allows extra constraints, supporting data, and fact boundaries. (Disclaimer applies)",
};

/** Human-readable level for product name (e.g. "standard level"). */
export function getLevelProductName(level: Level): string {
  return `${LEVEL_LABELS[level]} level`;
}

/** Format price for display (e.g. "€0.50"). */
export function formatLevelPrice(level: Level): string {
  return `€${LEVEL_PRICES[level].toFixed(2)}`;
}
