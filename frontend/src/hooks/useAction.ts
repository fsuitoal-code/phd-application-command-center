import { useState } from "react";
import { errorText } from "../format";

/**
 * Busy + error state for anything a click sends to the backend.
 *
 * Every mutation in the app goes through one of these, so a failure always
 * lands on screen next to the control that caused it (never an unhandled
 * rejection) and a slow request can't be double-submitted. `key` names which
 * of several controls is running — a row id, a proposal index — so only that
 * one shows as busy; `pending` holds it, `busy` is "anything running".
 */
export function useAction() {
  const [pending, setPending] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  /** Runs `fn`; resolves true on success, false (with `error` set) on failure. */
  async function run(fn: () => Promise<unknown>, key: unknown = true): Promise<boolean> {
    setPending(key);
    setError(null);
    try {
      await fn();
      return true;
    } catch (e) {
      setError(errorText(e));
      return false;
    } finally {
      setPending(null);
    }
  }

  return { busy: pending !== null, pending, error, setError, run };
}
