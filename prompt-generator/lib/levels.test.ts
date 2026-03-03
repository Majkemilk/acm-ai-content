import { describe, it, expect } from "vitest";
import {
  LEVELS,
  LEVEL_CENTS,
  LEVEL_LABELS,
  LEVEL_DESCRIPTIONS,
  LEVEL_PRICES,
  formatLevelPrice,
  getLevelProductName,
  type Level,
} from "./levels";

describe("levels", () => {
  describe("LEVELS", () => {
    it("contains exactly standard, advanced, expert", () => {
      expect(LEVELS).toEqual(["standard", "advanced", "expert"]);
    });
  });

  describe("LEVEL_CENTS", () => {
    it("has an entry for every level", () => {
      for (const level of LEVELS) {
        expect(LEVEL_CENTS).toHaveProperty(level);
        expect(typeof LEVEL_CENTS[level]).toBe("number");
      }
    });

    it("standard is 50, advanced 100, expert 300", () => {
      expect(LEVEL_CENTS.standard).toBe(50);
      expect(LEVEL_CENTS.advanced).toBe(100);
      expect(LEVEL_CENTS.expert).toBe(300);
    });
  });

  describe("LEVEL_LABELS", () => {
    it("has a non-empty label for every level", () => {
      for (const level of LEVELS) {
        expect(LEVEL_LABELS[level]).toBeDefined();
        expect(LEVEL_LABELS[level].length).toBeGreaterThan(0);
      }
    });

    it("matches expected labels", () => {
      expect(LEVEL_LABELS.standard).toBe("Standard");
      expect(LEVEL_LABELS.advanced).toBe("Advanced");
      expect(LEVEL_LABELS.expert).toBe("Expert");
    });
  });

  describe("LEVEL_DESCRIPTIONS", () => {
    it("has a non-empty description for every level", () => {
      for (const level of LEVELS) {
        expect(LEVEL_DESCRIPTIONS[level]).toBeDefined();
        expect(LEVEL_DESCRIPTIONS[level].length).toBeGreaterThan(0);
      }
    });
  });

  describe("LEVEL_PRICES", () => {
    it("matches LEVEL_CENTS in euros", () => {
      expect(LEVEL_PRICES.standard).toBe(0.5);
      expect(LEVEL_PRICES.advanced).toBe(1.0);
      expect(LEVEL_PRICES.expert).toBe(3.0);
    });
  });

  describe("formatLevelPrice", () => {
    it("formats each level as €X.XX", () => {
      expect(formatLevelPrice("standard")).toBe("€0.50");
      expect(formatLevelPrice("advanced")).toBe("€1.00");
      expect(formatLevelPrice("expert")).toBe("€3.00");
    });
  });

  describe("getLevelProductName", () => {
    it("returns label + ' level' for each level", () => {
      expect(getLevelProductName("standard")).toBe("Standard level");
      expect(getLevelProductName("advanced")).toBe("Advanced level");
      expect(getLevelProductName("expert")).toBe("Expert level");
    });
  });
});
