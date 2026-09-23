import { Link } from "react-router";
import { useTitle } from "../hooks/useTitle";

/** Any URL the app doesn't know — say so, rather than render a blank page. */
export default function NotFound({ message = "There's nothing at this address." }: { message?: string }) {
  useTitle("Not found");
  return (
    <div className="py-12 text-center">
      <p className="text-sm text-ink-subtle">{message}</p>
      <Link
        to="/"
        className="mt-3 inline-block text-sm text-ink underline decoration-hairline-strong underline-offset-2 transition-colors hover:decoration-ink"
      >
        Back to Programs
      </Link>
    </div>
  );
}
