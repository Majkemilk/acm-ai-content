import Link from "next/link";

const NAV_LINKS = [
  { href: "https://flowtaro.com", label: "Flowtaro" },
  { href: "https://flowtaro.com/hubs/marketplaces-products/", label: "Problem Fix & Find" },
  { href: "https://pl.flowtaro.com", label: "Problem Fix & Find (PL)" },
  { href: "/", label: "Prompt Generator", current: true },
  { href: "https://flowtaro.com", label: "EN" },
  { href: "https://pl.flowtaro.com", label: "PL" },
] as const;

export function SiteNav() {
  return (
    <header className="border-b border-[#e2e8f0] bg-white">
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 px-4 py-4 sm:flex-row sm:justify-between sm:gap-6">
        <a
          href="https://flowtaro.com/"
          className="shrink-0"
          aria-label="Flowtaro – home"
        >
          <img
            src="/images/logo.webp"
            alt="Flowtaro"
            className="h-12 w-auto sm:h-14"
          />
        </a>
        <nav
          className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-sm"
          aria-label="Main"
        >
          {NAV_LINKS.map((item) => {
            const isCurrent = item.current === true;
            const isExternal = item.href.startsWith("http");
            const className = `text-[#1e293b] hover:text-[#17266B] hover:underline ${isCurrent ? "font-semibold text-[#17266B]" : ""}`;
            if (isExternal) {
              return (
                <a
                  key={item.label}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={className}
                  {...(isCurrent && { "aria-current": "page" })}
                >
                  {item.label}
                </a>
              );
            }
            return (
              <Link
                key={item.label}
                href={item.href}
                className={className}
                {...(isCurrent && { "aria-current": "page" })}
              >
                {item.label}
              </Link>
            );
          }).reduce<React.ReactNode[]>((acc, node, i) => {
            if (i > 0) {
              acc.push(<span key={`sep-${i}`} className="text-[#94a3b8]" aria-hidden>|</span>);
            }
            acc.push(node);
            return acc;
          }, [])}
        </nav>
      </div>
    </header>
  );
}
