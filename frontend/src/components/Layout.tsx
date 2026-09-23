import { useEffect, useSyncExternalStore } from "react";
import { Link, useLocation } from "react-router";
import { useElementHeight } from "../hooks/useElementHeight";
import { researchStore } from "../research";
import { ResearchStatus } from "./ResearchStatus";
import { ThemeSwitch } from "./ThemeSwitch";
import { focusRing } from "./ui";

// Dashboard is a read-only cross-program view — agenda, attention list,
// checklist grid, comparison — over the same Programs data, not its own body
// of work.
const NAV = [
  { to: "/", label: "Programs" },
  { to: "/dashboard", label: "Dashboard" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  // A research pass outlives the page that started it, so the header carries it.
  const research = useSyncExternalStore(researchStore.subscribe, researchStore.get);
  // Program detail lives under /programs/:id — still the "Programs" section.
  const isActive = (to: string) =>
    to === "/" ? pathname === "/" || pathname.startsWith("/programs") : pathname === to;

  // The header's own height varies — the research strip adds a row — so a
  // page that wants to stick something (e.g. a program's progress checklist)
  // directly beneath it reads this rather than guessing a fixed offset.
  const [headerRef, headerH] = useElementHeight<HTMLElement>(research);
  useEffect(() => {
    document.documentElement.style.setProperty("--header-h", `${headerH}px`);
  }, [headerH]);

  return (
    <>
      <header
        ref={headerRef}
        className="sticky top-0 z-10 border-b border-hairline bg-canvas/90 backdrop-blur"
      >
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-2.5">
          {/* The app name sits a step below a page's own title (text-xl), so
              the page you're on is the heading that reads first. */}
          <Link to="/" className={`flex items-center gap-2 rounded ${focusRing}`}>
            <img src="/logo.png" alt="" className="h-9 w-9 rounded" />
            <span className="hidden font-display text-lg font-semibold tracking-tight sm:inline">
              PhD Command Center
            </span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            {NAV.map((n) => (
              <Link
                key={n.to}
                to={n.to}
                className={`rounded transition-colors ${focusRing} ${
                  isActive(n.to)
                    ? "font-medium text-ink"
                    : "text-ink-subtle hover:text-ink"
                }`}
              >
                {n.label}
              </Link>
            ))}
            <ThemeSwitch />
          </nav>
        </div>
        {research && <ResearchStatus run={research} />}
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </>
  );
}
