import { describe, it, expect } from "vitest";
import {
  getMetaPromptForLevel,
  META_PROMPT_STANDARD,
  META_PROMPT_ADVANCED,
  META_PROMPT_EXPERT,
} from "./metaPrompt";
import { LEVELS, type Level } from "./levels";

describe("getMetaPromptForLevel", () => {
  it("returns META_PROMPT_STANDARD for level standard", () => {
    expect(getMetaPromptForLevel("standard")).toBe(META_PROMPT_STANDARD);
  });

  it("returns META_PROMPT_ADVANCED for level advanced", () => {
    expect(getMetaPromptForLevel("advanced")).toBe(META_PROMPT_ADVANCED);
  });

  it("returns META_PROMPT_EXPERT for level expert", () => {
    expect(getMetaPromptForLevel("expert")).toBe(META_PROMPT_EXPERT);
  });

  it("returns a non-empty string for every level", () => {
    for (const level of LEVELS) {
      const prompt = getMetaPromptForLevel(level as Level);
      expect(prompt).toBeDefined();
      expect(typeof prompt).toBe("string");
      expect(prompt.length).toBeGreaterThan(0);
    }
  });

  it("returns different content for each level", () => {
    const standard = getMetaPromptForLevel("standard");
    const advanced = getMetaPromptForLevel("advanced");
    const expert = getMetaPromptForLevel("expert");
    expect(standard).not.toBe(advanced);
    expect(advanced).not.toBe(expert);
    expect(standard).not.toBe(expert);
  });
});
