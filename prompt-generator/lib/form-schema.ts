import { z } from "zod";
import { LEVELS, LEVEL_CENTS, type Level } from "@/lib/levels";

const formSchemaObject = z.object({
  level: z.enum(LEVELS),
  topic: z.string().optional(),
  objective: z.string().optional(),
  audience: z.string().optional(),
  context: z.string().optional(),
  constraints: z.string().optional(),
  format: z.string().optional(),
  supportingData: z.string().optional(),
  factsToAdhereTo: z.string().optional(),
  expertAcknowledgement: z.boolean().optional(),
});

export const formSchema = formSchemaObject.superRefine((data, ctx) => {
  const { level } = data;
  if (!data.topic?.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Topic must be at least 3 characters",
      path: ["topic"],
    });
  } else if (data.topic.trim().length < 3) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Topic must be at least 3 characters",
      path: ["topic"],
    });
  }
  if (!data.objective?.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Main objective is required",
      path: ["objective"],
    });
  } else if (data.objective.trim().length < 5) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Main objective must be at least 5 characters",
      path: ["objective"],
    });
  }
  if (!data.context?.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Context is required",
      path: ["context"],
    });
  }
  if (level === "advanced" || level === "expert") {
    if (!data.audience?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Target audience is required",
        path: ["audience"],
      });
    }
    if (!data.format?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Preferred output format is required",
        path: ["format"],
      });
    }
  }
  if (level === "expert") {
    if (!data.factsToAdhereTo?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Facts to strictly adhere to is required for Expert level",
        path: ["factsToAdhereTo"],
      });
    }
    if (data.expertAcknowledgement !== true) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "You must acknowledge the disclaimer",
        path: ["expertAcknowledgement"],
      });
    }
  }
});

export type FormData = z.infer<typeof formSchemaObject>;

/** Re-export for consumers that only need level + cents (e.g. create-checkout). */
export type { Level } from "@/lib/levels";
export { LEVEL_CENTS } from "@/lib/levels";
