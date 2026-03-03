import { describe, it, expect } from "vitest";
import { formSchema } from "./form-schema";
import { LEVELS, type Level } from "./levels";

const baseValid = {
  topic: "Marketing",
  objective: "Get 5 ideas",
  context: "Small business, low budget",
};

describe("formSchema level validation", () => {
  it("accepts level standard", () => {
    const result = formSchema.safeParse({
      ...baseValid,
      level: "standard",
    });
    expect(result.success).toBe(true);
  });

  it("accepts level advanced", () => {
    const result = formSchema.safeParse({
      ...baseValid,
      level: "advanced",
      audience: "SME owners",
      format: "checklist",
    });
    expect(result.success).toBe(true);
  });

  it("accepts level expert", () => {
    const result = formSchema.safeParse({
      ...baseValid,
      level: "expert",
      audience: "Lawyers",
      format: "step-by-step list",
      factsToAdhereTo: "Do not invent case law",
      expertAcknowledgement: true,
    });
    expect(result.success).toBe(true);
  });

  it("rejects invalid level", () => {
    const result = formSchema.safeParse({
      ...baseValid,
      level: "invalid",
    });
    expect(result.success).toBe(false);
  });

  it("rejects level basic (old value)", () => {
    const result = formSchema.safeParse({
      ...baseValid,
      level: "basic",
    });
    expect(result.success).toBe(false);
  });

  it("for advanced requires audience and format", () => {
    const withoutAudience = formSchema.safeParse({
      ...baseValid,
      level: "advanced",
      format: "checklist",
    });
    expect(withoutAudience.success).toBe(false);

    const withoutFormat = formSchema.safeParse({
      ...baseValid,
      level: "advanced",
      audience: "SME",
    });
    expect(withoutFormat.success).toBe(false);

    const withBoth = formSchema.safeParse({
      ...baseValid,
      level: "advanced",
      audience: "SME",
      format: "checklist",
    });
    expect(withBoth.success).toBe(true);
  });

  it("for expert requires factsToAdhereTo and expertAcknowledgement", () => {
    const withoutFacts = formSchema.safeParse({
      ...baseValid,
      level: "expert",
      audience: "Lawyers",
      format: "list",
      expertAcknowledgement: true,
    });
    expect(withoutFacts.success).toBe(false);

    const withoutAcknowledgement = formSchema.safeParse({
      ...baseValid,
      level: "expert",
      audience: "Lawyers",
      format: "list",
      factsToAdhereTo: "No inventing",
    });
    expect(withoutAcknowledgement.success).toBe(false);
  });
});

describe("formSchema level enum", () => {
  it("only allows LEVELS values", () => {
    const validPayloads: Record<Level, object> = {
      standard: { ...baseValid, level: "standard" },
      advanced: {
        ...baseValid,
        level: "advanced",
        audience: "SME owners",
        format: "checklist",
      },
      expert: {
        ...baseValid,
        level: "expert",
        audience: "Lawyers",
        format: "list",
        factsToAdhereTo: "Do not invent",
        expertAcknowledgement: true,
      },
    };
    for (const level of LEVELS) {
      const result = formSchema.safeParse(validPayloads[level]);
      expect(result.success, `level "${level}" should be valid`).toBe(true);
    }
  });
});
