import { useEffect } from "react";

const APP = "PhD Command Center";

/** The browser tab's title, so several open tabs can be told apart. */
export function useTitle(title: string | null) {
  useEffect(() => {
    document.title = title ? `${title} · ${APP}` : APP;
  }, [title]);
}
