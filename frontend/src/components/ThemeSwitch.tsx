import { useEffect, useState } from "react";
import { focusRing } from "./ui";

const KEY = "phdtracker.theme";

/** Read once, in the same order index.html's inline script uses. */
function initial(): "light" | "dark" {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* private window or blocked storage — fall through to the OS preference */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/**
 * Night mode. Defaults to the OS preference and remembers an explicit choice
 * from then on. All it does is set `data-theme` on <html>; the values live in
 * index.css, so nothing else in the app is theme-aware.
 */
export function ThemeSwitch() {
  const [theme, setTheme] = useState<"light" | "dark">(initial);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* the choice just won't survive a reload */
    }
  }, [theme]);

  const dark = theme === "dark";
  return (
    <button
      onClick={() => setTheme(dark ? "light" : "dark")}
      title={dark ? "Switch to day" : "Switch to night"}
      aria-label={dark ? "Switch to day mode" : "Switch to night mode"}
      className={`-m-1 rounded-md p-1 text-ink-subtle transition-colors hover:text-ink ${focusRing}`}
    >
      {dark ? (
        // Sun — click to go back to day.
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="1.8" />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
            <line
              key={deg}
              x1="12"
              y1="1.6"
              x2="12"
              y2="4.1"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              transform={`rotate(${deg} 12 12)`}
            />
          ))}
        </svg>
      ) : (
        // Crescent — click to go to night.
        <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M20.1 14.6A8.4 8.4 0 0 1 9.4 3.9a8.4 8.4 0 1 0 10.7 10.7Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </button>
  );
}
