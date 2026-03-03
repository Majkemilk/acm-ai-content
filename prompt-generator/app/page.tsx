"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useEffect, useRef, useState } from "react";

import { formSchema, type FormData, type Level } from "@/lib/form-schema";
import {
  LEVEL_PRICES,
  LEVEL_LABELS,
  formatLevelPrice,
} from "@/lib/levels";
import aiChatTools from "./ai-chat-tools.json";

const FORMAT_OPTIONS_STANDARD = [
  "step-by-step list",
  "table",
  "checklist",
  "instructions",
  "analysis",
] as const;

const FORMAT_OPTIONS_EXPERT = [
  "AI's choice",
  ...FORMAT_OPTIONS_STANDARD,
] as const;

const TOOLTIPS = {
  level:
    "Standard: short prompts. Advanced: audience + format. Expert: in-depth, fact-checking and optional constraints.",
  topic:
    "Main subject in a few words, e.g. 'Marketing strategy for a startup' or 'EU data protection basics'.",
  objective:
    "What you want from the AI, e.g. 'Generate 5 social media ideas' or 'Explain in 3 short paragraphs'.",
  audience:
    "Who will use the answer (generated prompt), e.g. 'Me. I'm a beginner marketer', 'SME owners', 'Students'.",
  context:
    "Background, situation and others: budget, deadline, industry, or why you need this.",
  constraints:
    "Limits you care about: budget, time, tone, tools. Leave blank if none.",
  format:
    "Choose how the AI should format its reply when you use this prompt in a new chat.",
  supportingData:
    "Paste numbers, text or facts the AI must use. You can also attach files in the chat later.",
  factsToAdhereTo:
    "What the AI must not invent, e.g. 'Do not invent case law' or 'Use only the numbers I provided'.",
  expertAcknowledgement:
    "Expert prompts are for support only. For important decisions, always check with a qualified professional.",
  submitButton:
    "Pay once and get your prompt. Copy the prompt you'll generate.\nBe careful. It won't be shown again.",
} as const;

const ORDINARY_PROMPT_EXAMPLE = `Evaluate this startup idea: Pay-per-use shopping for seniors.
I'm considering providing this service in Tampa, Florida. I have a car and small funds to start with. My time is limited to 5-6 hours per week.
Assess the idea's potential and revenue streams. Rate its chance of success and viability on a scale of 1-10.`;

const FPG_PROMPT_BY_LEVEL: Record<Level, string> = {
  standard:
    "You are a business consultant. Your main objective is to assess the potential and revenue streams of a startup idea focused on pay-per-use shopping for seniors. The context is that you are considering providing this service in Tampa, Florida, with limited funds and a commitment of 5-6 hours per week. Your task is to evaluate the idea's chance of success and viability on a scale of 1-10. If (...). Please ask 1–3 clarification questions if (...). The answer must use uncertainty phrases when needed.",
  advanced: `ROLE: You are a business analyst specializing in startup evaluation for niche markets.
OBJECTIVE: Assess the potential and revenue streams of the startup idea: pay-per-use shopping for seniors.
CONTEXT/INPUT: You are considering providing this service in Tampa, Florida, and you are a solopreneur with limited time (5-6 hours per week), a car, and small funds to start.
TASK: Evaluate the startup idea, rate its chance of success and viability on a scale of 1-10, and provide an analysis of potential revenue streams.
OUTPUT FORMAT: Please provide your answer in a structured analysis format.

Consider the market demand for such a service, potential competition in Tampa, and any regulatory factors that may affect the business. If (...). Do not guess; if (...). If external knowledge is necessary for your analysis, please indicate the sources you used or (...). Include 1–3 edge cases or (...). You may ask 1–3 clarification questions if (...). Briefly verify critical points before finalising your answer. (...)
`,
  expert: `ROLE: Multidisciplinary team of business strategists and market analysts.
OBJECTIVE: Assess the potential and revenue streams of the startup idea: Pay-per-use shopping for seniors in Tampa, Florida. Rate its chance of success and viability on a scale of 1-10.
CONTEXT/INPUT: You are a solopreneur with a car and small funds to start with, considering providing this service in Tampa, Florida. Your time is limited to 5-6 hours per week.
TASK: Evaluate the startup idea, identify potential revenue streams, and rate its success and viability. Consider constraints and provide actionable insights.
OUTPUT FORMAT: Provide a structured analysis with a step-by-step evaluation, rating scale, and recommendations.

Consider market demand, competition, regulatory factors, and constraints. If (...). Do not guess; state uncertainty when something cannot be verified (e.g. "I am not certain", "I cannot verify"). For external claims, cite sources or (...). Work step-by-step; if (...). For this assessment, use a short chain-of-verification: analysis, then questions, then reanalysis, then final answer with confidence level. Include 2–5 edge cases or (...). Before finalising, verify that the objective is met and the rules are followed. Independently verify critical decisions. (...)
`,
};

function FieldHint({ text }: { text: string }) {
  return <p className="mt-0.5 text-sm italic text-[#64748b] whitespace-pre-line">{text}</p>;
}

const defaultValuesByLevel: Record<Level, Partial<FormData>> = {
  standard: {
    level: "standard",
    topic: "",
    objective: "",
    context: "",
    audience: "",
    constraints: "",
    format: undefined,
    supportingData: "",
    factsToAdhereTo: "",
    expertAcknowledgement: false,
  },
  advanced: {
    level: "advanced",
    topic: "",
    objective: "",
    audience: "",
    context: "",
    constraints: "",
    format: "step-by-step list",
    supportingData: "",
    factsToAdhereTo: "",
    expertAcknowledgement: false,
  },
  expert: {
    level: "expert",
    topic: "",
    objective: "",
    audience: "",
    context: "",
    constraints: "",
    format: "AI's choice",
    supportingData: "",
    factsToAdhereTo: "",
    expertAcknowledgement: false,
  },
};

export default function Home() {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      level: "standard",
      ...defaultValuesByLevel.standard,
    },
  });

  const level = watch("level") as Level;
  const prevLevelRef = useRef<Level>(level);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [examplePreviewLevel, setExamplePreviewLevel] = useState<Level>("standard");

  const formatOptions =
    level === "expert" ? FORMAT_OPTIONS_EXPERT : FORMAT_OPTIONS_STANDARD;

  const price = useMemo(
    () => (level ? LEVEL_PRICES[level] : LEVEL_PRICES.standard),
    [level]
  );

  useEffect(() => {
    if (prevLevelRef.current !== level) {
      prevLevelRef.current = level;
      const defaults = defaultValuesByLevel[level];
      reset(defaults as FormData);
    }
  }, [level, reset]);

  const onSubmit = async (data: FormData) => {
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const res = await fetch("/api/create-checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const json = await res.json().catch(() => ({} as Record<string, unknown>));
      if (!res.ok) {
        const message = typeof json?.error === "string" ? json.error : "Checkout could not be started. Please try again.";
        setSubmitError(message);
        return;
      }
      const url = json?.url;
      if (url && typeof url === "string") {
        window.location.href = url;
        return;
      }
      setSubmitError("No payment URL was returned. Please try again.");
    } catch {
      setSubmitError("A network error occurred. Please check your connection and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputBase =
    "mt-1 block w-full rounded-md border border-[#e2e8f0] px-3 py-2 shadow-sm focus:border-[#17266B] focus:outline-none focus:ring-1 focus:ring-[#17266B] sm:text-sm text-[#1e293b]";
  const inputError =
    "border-red-500 focus:border-red-500 focus:ring-red-500";
  const labelBase = "block text-sm font-medium text-[#1e293b]";
  const requiredMark = <span className="text-red-600" aria-hidden="true"> *</span>;

  return (
    <div
      className="min-h-screen bg-white py-8 px-4 sm:px-6 lg:px-8"
      style={{
        color: "#1e293b",
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      <div className="mx-auto max-w-3xl">
        {/* Logo – same as main site */}
        <div className="mb-8 text-center">
          <a href="/" className="inline-block">
            <img
              src="/images/logo.webp"
              alt="Flowtaro"
              className="mx-auto block h-auto w-56"
            />
          </a>
        </div>

        <div className="rounded-xl border border-[#e2e8f0] bg-white py-8 px-6 shadow-sm sm:px-10 sm:py-12">
          {/* Hero */}
          <h1 className="text-2xl font-bold tracking-tight text-[#17266B] sm:text-3xl">
            Flowtaro Prompt Generator
          </h1>
          <p className="mt-4 text-[#64748b] text-base">
            Generate high‑quality, ready‑to‑use prompts for{" "}
            {(aiChatTools as { name: string; url: string }[]).map((tool, i, arr) => (
              <span key={tool.name}>
                <a href={tool.url} target="_blank" rel="noopener noreferrer" className="text-[#17266B] underline hover:no-underline">{tool.name}</a>
                {i < arr.length - 1 ? ", " : " or other AI models."}
              </span>
            ))}
            <br />
            One prompt, one payment. No subscription. Unbeatable value.
          </p>

          {/* What makes Flowtaro different? */}
          <section className="mt-8 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-4 sm:p-5">
            <h2 className="text-xl font-semibold text-[#17266B] mb-2">
              What makes Flowtaro different?
            </h2>
            <p className="text-sm text-[#334155] leading-relaxed">
              Unlike basic prompt templates or expensive AI writing tools, Flowtaro adapts to your needs. Most generators give you one-size-fits-all templates – we give you a prompt engineered specifically for your topic, audience, and desired depth. Whether you need a quick answer or a deep expert-level analysis, our system automatically adjusts the instructions to match your level (Standard, Advanced, Expert). No more guessing how to structure your question – we do it for you.
            </p>
          </section>

          {/* How it works */}
          <section className="mt-6 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-4 sm:p-5">
            <h2 className="text-xl font-semibold text-[#17266B] mb-2">
              How it works
            </h2>
            <ol className="list-decimal list-inside space-y-3 text-sm text-[#334155] leading-relaxed">
              <li>
                <strong className="text-[#1e293b]">Choose your level</strong> – Standard (Quick, concise prompts for everyday questions. Ideal for students, hobbyists.), Advanced (Balanced prompts for business, education, and planning. Includes target audience and format selection.), or Expert (In‑depth prompts with strict fact‑checking for legal, financial, and medical topics. Allows extra constraints, supporting data, and fact boundaries – disclaimer applies).
              </li>
              <li>
                <strong className="text-[#1e293b]">Fill in the fields</strong> – tell us what you need, who it&apos;s for, and any constraints.
              </li>
              <li>
                <strong className="text-[#1e293b]">Pay once</strong> – no subscription, just a small fee per prompt.
              </li>
              <li>
                <strong className="text-[#1e293b]">Get your prompt instantly</strong> – you&apos;ll see it on the screen right after payment. <strong className="font-bold text-[#17266B]">Be sure to copy it</strong> – it won&apos;t be accessible again after you close the session.
              </li>
              <li>
                <strong className="text-[#1e293b]">Paste it into</strong>{" "}
                {(aiChatTools as { name: string; url: string }[]).map((tool, i, arr) => (
                  <span key={tool.name}>
                    <a href={tool.url} target="_blank" rel="noopener noreferrer" className="text-[#17266B] underline hover:no-underline">{tool.name}</a>
                    {i < arr.length - 1 ? ", " : " or other AI models – and get the answer you need."}
                  </span>
                ))}
              </li>
            </ol>
          </section>

          {/* What you get – merged with level descriptions, safety-focused */}
          <section className="mt-6 mb-6 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-4 sm:p-5">
            <h2 className="text-xl font-semibold text-[#17266B] mb-2">
              What you get (and what you don&apos;t)
            </h2>
            <p className="text-sm text-[#334155] leading-relaxed mb-4">
              You don&apos;t get an AI answer here—you get a <strong className="text-[#1e293b]">ready-to-use question</strong> that you copy and paste into any AI chat. Our prompts are built to steer the AI toward clear, structured, and more reliable answers while encouraging it to say when it&apos;s unsure. Think of it as a safer way to get useful output: the prompt is designed to reduce guesswork and keep responses aligned with your topic and constraints. Once generated, it appears on screen—remember to copy it, as it won&apos;t be available again.
            </p>
            <p className="text-sm font-medium text-[#17266B] mb-2">
              What you get by level
            </p>
            <ul className="space-y-2 text-sm text-[#334155] leading-relaxed">
              <li>
                <strong className="text-[#1e293b]">Standard</strong> — Short, clear prompts for everyday use. Suited to students and hobbyists. Instructions nudge the AI toward concise, relevant answers and brief uncertainty wording when needed.
              </li>
              <li>
                <strong className="text-[#1e293b]">Advanced</strong> — Balanced prompts for work, study, or planning. You specify who the answer is for and how you want it (e.g. list, table). The prompt encourages accuracy and consistent formatting for easier, more trustworthy use.
              </li>
              <li>
                <strong className="text-[#1e293b]">Expert</strong> — In-depth prompts for sensitive or high-stakes topics (e.g. legal, financial, medical). Supports extra constraints, your own data, and strict “do not invent” rules. The prompt is built to support a safer, more reliable outcome by stressing verification and clear uncertainty—so the AI is more likely to flag what it cannot confirm. This does not replace professional advice; always verify critical decisions with a qualified expert.
              </li>
            </ul>
          </section>

          {/* Preview example for level – independent from form level */}
          <div className="mt-6">
            <p className="text-sm font-medium text-[#1e293b] mb-2">
              Preview example for level:
            </p>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Select level to preview example">
              {(["standard", "advanced", "expert"] as const).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => setExamplePreviewLevel(lvl)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    examplePreviewLevel === lvl
                      ? "bg-[#17266B] text-white shadow-sm"
                      : "bg-white border border-[#e2e8f0] text-[#334155] hover:border-[#17266B] hover:text-[#17266B]"
                  }`}
                >
                  {lvl.charAt(0).toUpperCase() + lvl.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Comparison example – right card uses examplePreviewLevel */}
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#64748b]">
                Example of an ordinary prompt
              </p>
              <p className="mt-1 font-mono text-sm text-[#1e293b] leading-relaxed whitespace-pre-line">
                {ORDINARY_PROMPT_EXAMPLE}
              </p>
            </div>
            <div className="rounded-lg border border-[#17266B]/40 bg-[#f1f5f9] p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#17266B]">
                Example of a generated prompt ({examplePreviewLevel.charAt(0).toUpperCase() + examplePreviewLevel.slice(1)})
              </p>
              <p className="mt-1 text-sm text-[#334155] leading-relaxed whitespace-pre-line">
                {FPG_PROMPT_BY_LEVEL[examplePreviewLevel]}
              </p>
            </div>
          </div>

          {/* Now fill in the form – disclaimer + CTA-style encouragement */}
          <section className="mt-6 mb-2 rounded-lg border border-[#e2e8f0] bg-[#f1f5f9] p-4 sm:p-5">
            <h2 className="text-lg font-semibold text-[#17266B] mb-2">
              Now fill in the form below
            </h2>
            <p className="text-sm text-[#64748b] mb-2 italic">
              We don&apos;t collect or store any of your data at this address; the prompt is generated on your device and we never see your topic or email.
            </p>
            <p className="text-sm text-[#334155] leading-relaxed">
              Pick your level, add your topic, and get your prompt in seconds—no account required. Your turn: tweak the options and run with it. {'"The proof is in the pudding"—see for yourself!'}
            </p>
          </section>

          {/* Select your level – single block: description + radios + hint */}
          <section className="mt-6 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-4 sm:p-5">
            <h2 className="text-lg font-semibold text-[#17266B] mb-1">
              Select your level
            </h2>
            <p className="text-sm text-[#64748b] mb-4">
              Standard: short prompts. Advanced: audience + format. Expert: in-depth, fact-checking and optional constraints.
            </p>
            <div className="space-y-2" role="group" aria-label="Select level">
              {(
                [
                  { value: "standard" as const, label: `${LEVEL_LABELS.standard} (${formatLevelPrice("standard")})` },
                  { value: "advanced" as const, label: `${LEVEL_LABELS.advanced} (${formatLevelPrice("advanced")})` },
                  { value: "expert" as const, label: `${LEVEL_LABELS.expert} (${formatLevelPrice("expert")})` },
                ] as const
              ).map(({ value, label }) => (
                <label
                  key={value}
                  className="flex cursor-pointer items-center gap-3 rounded-md border border-transparent p-2.5 transition hover:bg-white has-[:checked]:border-[#17266B] has-[:checked]:bg-white has-[:checked]:shadow-sm"
                >
                  <input
                    type="radio"
                    value={value}
                    {...register("level")}
                    className="h-4 w-4 border-[#e2e8f0] text-[#17266B] focus:ring-[#17266B]"
                  />
                  <span className="text-sm font-medium text-[#1e293b]">
                    {label}
                  </span>
                </label>
              ))}
            </div>
            <p className="mt-3 text-sm text-[#64748b] italic">
              See the section above for what each level includes.
            </p>
          </section>

          <form
            onSubmit={handleSubmit(onSubmit)}
            className="mt-8 space-y-6"
          >
            <p className="text-sm text-[#64748b]">
              Fields marked with <span className="text-red-600">*</span> are required.
            </p>

            {/* Topic – all levels */}
            <div>
              <label htmlFor="topic" className={labelBase}>
                Topic{requiredMark}
              </label>
              <FieldHint text={TOOLTIPS.topic} />
              <input
                id="topic"
                type="text"
                {...register("topic")}
                className={`${inputBase} ${errors.topic ? inputError : ""}`}
                aria-invalid={!!errors.topic}
                aria-required
              />
              {errors.topic && (
                <p className="mt-1 text-sm text-red-600" role="alert">
                  {errors.topic.message}
                </p>
              )}
            </div>

            {/* Main objective – all levels */}
            <div>
              <label htmlFor="objective" className={labelBase}>
                Main objective{requiredMark}
              </label>
              <FieldHint text={TOOLTIPS.objective} />
              <input
                id="objective"
                type="text"
                {...register("objective")}
                className={`${inputBase} ${errors.objective ? inputError : ""}`}
                aria-invalid={!!errors.objective}
                aria-required
              />
              {errors.objective && (
                <p className="mt-1 text-sm text-red-600" role="alert">
                  {errors.objective.message}
                </p>
              )}
            </div>

            {/* Target audience – Advanced & Expert */}
            {(level === "advanced" || level === "expert") && (
              <div>
                <label htmlFor="audience" className={labelBase}>
                  Target audience{requiredMark}
                </label>
                <FieldHint text={TOOLTIPS.audience} />
                <input
                  id="audience"
                  type="text"
                  {...register("audience")}
                  className={`${inputBase} ${errors.audience ? inputError : ""}`}
                  aria-invalid={!!errors.audience}
                  aria-required
                />
                {errors.audience && (
                  <p className="mt-1 text-sm text-red-600" role="alert">
                    {errors.audience.message}
                  </p>
                )}
              </div>
            )}

            {/* Context – all levels */}
            <div>
              <label htmlFor="context" className={labelBase}>
                Context{requiredMark}
              </label>
              <FieldHint text={TOOLTIPS.context} />
              <textarea
                id="context"
                rows={4}
                {...register("context")}
                className={`${inputBase} ${errors.context ? inputError : ""}`}
                aria-invalid={!!errors.context}
                aria-required
              />
              {errors.context && (
                <p className="mt-1 text-sm text-red-600" role="alert">
                  {errors.context.message}
                </p>
              )}
            </div>

            {/* Constraints – Advanced & Expert, optional */}
            {(level === "advanced" || level === "expert") && (
              <div>
                <label htmlFor="constraints" className={labelBase}>
                  Constraints (optional)
                </label>
                <FieldHint text={TOOLTIPS.constraints} />
                <textarea
                  id="constraints"
                  rows={3}
                  {...register("constraints")}
                  className={inputBase}
                />
              </div>
            )}

            {/* Preferred output format – Advanced & Expert */}
            {(level === "advanced" || level === "expert") && (
              <div>
                <label htmlFor="format" className={labelBase}>
                  Preferred output format{requiredMark}
                </label>
                <FieldHint text={TOOLTIPS.format} />
                <select
                  id="format"
                  {...register("format")}
                  className={`${inputBase} ${errors.format ? inputError : ""}`}
                  aria-invalid={!!errors.format}
                  aria-required
                >
                  {formatOptions.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
                {errors.format && (
                  <p className="mt-1 text-sm text-red-600" role="alert">
                    {errors.format.message}
                  </p>
                )}
              </div>
            )}

            {/* Expert-only: Facts to strictly adhere to (required) */}
            {level === "expert" && (
              <div>
                <label htmlFor="factsToAdhereTo" className={labelBase}>
                  Facts to strictly adhere to / avoid inventing{requiredMark}
                </label>
                <FieldHint text={TOOLTIPS.factsToAdhereTo} />
                <textarea
                  id="factsToAdhereTo"
                  rows={3}
                  {...register("factsToAdhereTo")}
                  className={`${inputBase} ${errors.factsToAdhereTo ? inputError : ""}`}
                  aria-invalid={!!errors.factsToAdhereTo}
                  aria-required
                />
                {errors.factsToAdhereTo && (
                  <p className="mt-1 text-sm text-red-600" role="alert">
                    {errors.factsToAdhereTo.message}
                  </p>
                )}
              </div>
            )}

            {/* Expert-only: Supporting data (optional) */}
            {level === "expert" && (
              <div>
                <label htmlFor="supportingData" className={labelBase}>
                  Supporting data (optional)
                </label>
                <FieldHint text={TOOLTIPS.supportingData} />
                <textarea
                  id="supportingData"
                  rows={3}
                  {...register("supportingData")}
                  className={inputBase}
                />
              </div>
            )}

            {/* Expert acknowledgement checkbox */}
            {level === "expert" && (
              <div className={`rounded-lg border p-4 ${errors.expertAcknowledgement ? "border-red-500 bg-red-50/50" : "border-[#e2e8f0] bg-[#f8fafc]"}`}>
                <label className="flex cursor-pointer items-start gap-3">
                  <input
                    type="checkbox"
                    {...register("expertAcknowledgement")}
                    className="mt-1 h-4 w-4 rounded border-[#e2e8f0] text-[#17266B] focus:ring-[#17266B]"
                    aria-invalid={!!errors.expertAcknowledgement}
                    aria-required
                  />
                  <span className="text-sm text-[#334155]">
                    I acknowledge that this prompt is not a substitute for
                    professional advice and I will verify all critical
                    information.{requiredMark}
                  </span>
                </label>
                <FieldHint text={TOOLTIPS.expertAcknowledgement} />
                {errors.expertAcknowledgement && (
                  <p className="mt-1 text-sm text-red-600" role="alert">
                    {errors.expertAcknowledgement.message}
                  </p>
                )}
              </div>
            )}

            {/* Submit */}
            <div className="pt-4">
              {submitError && (
                <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
                  {submitError}
                </p>
              )}
              <button
                type="submit"
                disabled={
                  (level === "expert" && !watch("expertAcknowledgement")) || isSubmitting
                }
                className="w-full rounded-md bg-[#17266B] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#152558] focus:outline-none focus:ring-2 focus:ring-[#17266B] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Redirecting to payment…" : `Generate prompt – €${price.toFixed(2)}`}
              </button>
              <FieldHint text={TOOLTIPS.submitButton} />
            </div>

            {/* Legal disclaimer */}
            <p className="text-xs text-[#64748b] leading-relaxed">
              Disclaimer: The generated prompt is a tool for querying AI and does
              not constitute legal, financial, or medical advice. Always consult
              a qualified professional for decisions in high‑stakes areas.
            </p>
          </form>

          {/* Footer – same as other Flowtaro pages */}
          <footer className="mt-10 pt-6 border-t border-[#e2e8f0] text-center">
            <p className="text-sm text-[#64748b]">
              © 2026 Flowtaro.{" "}
              <a href="/privacy.html" className="text-[#64748b] hover:text-[#17266B]">
                Privacy Policy
              </a>
            </p>
          </footer>
        </div>
      </div>
    </div>
  );
}
