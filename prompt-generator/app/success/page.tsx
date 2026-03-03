"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState, Suspense } from "react";
import Link from "next/link";

type State =
  | { status: "loading" }
  | { status: "success"; prompt: string }
  | { status: "error"; message: string };

function SuccessContent() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [state, setState] = useState<State>({ status: "loading" });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!sessionId?.trim()) {
      setState({
        status: "error",
        message: "Missing session ID. Did you complete the payment?",
      });
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `/api/get-prompt?session_id=${encodeURIComponent(sessionId.trim())}`
        );
        const data = await res.json().catch(() => ({} as Record<string, unknown>));

        if (cancelled) return;

        if (!res.ok) {
          const msg =
            typeof data?.error === "string"
              ? data.error
              : "Something went wrong. Please try again from the start.";
          setState({ status: "error", message: msg });
          return;
        }

        const prompt = typeof data?.prompt === "string" ? data.prompt : "";
        if (!prompt) {
          setState({
            status: "error",
            message: "No prompt was returned. Please contact support.",
          });
          return;
        }

        setState({ status: "success", prompt });
      } catch {
        if (cancelled) return;
        setState({
          status: "error",
          message: "A network error occurred. Please check your connection and try again.",
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const copyToClipboard = useCallback(() => {
    if (state.status !== "success") return;
    navigator.clipboard.writeText(state.prompt).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      },
      () => {}
    );
  }, [state]);

  return (
    <div
      className="min-h-screen bg-white py-8 px-4 sm:px-6 lg:px-8"
      style={{
        color: "#1e293b",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 text-center">
          <Link href="/" className="inline-block">
            <img
              src="/images/logo.webp"
              alt="Flowtaro"
              className="mx-auto block h-auto w-56"
            />
          </Link>
        </div>

        <div className="rounded-xl border border-[#e2e8f0] bg-white py-8 px-6 shadow-sm sm:px-10 sm:py-12">
          <h1 className="text-2xl font-bold tracking-tight text-[#17266B] sm:text-3xl">
            Payment successful
          </h1>
          <p className="mt-2 text-[#64748b] text-base">
            Your prompt is ready. Copy it below – it will only be shown once.
          </p>

          {state.status === "loading" && (
            <div className="mt-8 flex flex-col items-center justify-center gap-4 py-12">
              <div
                className="h-10 w-10 animate-spin rounded-full border-2 border-[#17266B] border-t-transparent"
                aria-hidden
              />
              <p className="text-sm text-[#64748b]">
                Generating your prompt…
              </p>
            </div>
          )}

          {state.status === "error" && (
            <div className="mt-8 rounded-lg border border-red-200 bg-red-50 px-4 py-4">
              <p className="text-sm font-medium text-red-800" role="alert">
                {state.message}
              </p>
              <Link
                href="/"
                className="mt-4 inline-block rounded-md bg-[#17266B] px-4 py-2 text-sm font-semibold text-white hover:bg-[#152558] focus:outline-none focus:ring-2 focus:ring-[#17266B] focus:ring-offset-2"
              >
                Back to generator
              </Link>
            </div>
          )}

          {state.status === "success" && (
            <>
              <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
                <p className="text-sm font-medium text-amber-900">
                  This prompt will only be shown once. Copy it now – it
                  won&apos;t be accessible again after you leave this page.
                </p>
              </div>

              <div className="mt-6">
                <label
                  htmlFor="prompt-output"
                  className="block text-sm font-medium text-[#1e293b]"
                >
                  Your prompt
                </label>
                <textarea
                  id="prompt-output"
                  readOnly
                  rows={12}
                  className="mt-2 block w-full rounded-md border border-[#e2e8f0] bg-[#f8fafc] px-3 py-3 font-mono text-sm text-[#1e293b] shadow-sm focus:border-[#17266B] focus:outline-none focus:ring-1 focus:ring-[#17266B]"
                  value={state.prompt}
                  aria-describedby="prompt-warning"
                />
                <p id="prompt-warning" className="sr-only">
                  Copy this prompt; it will not be shown again.
                </p>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={copyToClipboard}
                  className="rounded-md bg-[#17266B] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#152558] focus:outline-none focus:ring-2 focus:ring-[#17266B] focus:ring-offset-2"
                >
                  {copied ? "Copied!" : "Copy to clipboard"}
                </button>
                <Link
                  href="/"
                  className="text-sm font-medium text-[#17266B] hover:underline"
                >
                  Generate another prompt
                </Link>
              </div>
            </>
          )}
        </div>

        <footer className="mt-10 pt-6 border-t border-[#e2e8f0] text-center">
          <p className="text-sm text-[#64748b]">
            © 2026 Flowtaro.{" "}
            <a
              href="/privacy.html"
              className="text-[#64748b] hover:text-[#17266B]"
            >
              Privacy Policy
            </a>
          </p>
        </footer>
      </div>
    </div>
  );
}

function SuccessLoadingFallback() {
  return (
    <div className="min-h-screen bg-white py-8 px-4 flex items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-[#17266B] border-t-transparent" />
    </div>
  );
}

export default function SuccessPage() {
  return (
    <Suspense fallback={<SuccessLoadingFallback />}>
      <SuccessContent />
    </Suspense>
  );
}
